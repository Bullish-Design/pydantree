"""Phase 9 — the nix real-user consumer (shared by every run shape).

The extraction task: the **devenv fleet inventory** over the vendored fleet
subset (tests/fixtures/nix/fleet/) — packages / env / scripts / tasks /
enabled switches / enterShell+enterTest, aggregated per repo. Hand truth in
ground_truth.json, written BEFORE the models (nix semantics).

The A surface does the extraction: two generic models (every binding, every
list) with field captures, source_meta, and validate_with checks active. Two
classes of CONTEXT are resolved by consumer helpers over the tree (the honest
escape hatches, documented in FINDINGS):

  1. the FULL dotted path of a binding (attrset nesting is not expressible as
     a capture) — `dotted_path`, walking ancestor bindings at the node;
  2. LINE NUMBERS — nix's grammar has an ecosystem position bug (tree-sitter
     0.26 + this grammar's scanner): reading node start POINTS on large
     multiline-string-heavy files (flora 526 lines) returns garbage or
     crashes; node start BYTES and texts are reliable. The consumer computes
     every line from the byte offset (`src[:start_byte].count(b'\\n') + 1`),
     pairing walk entries with model rows in document order. Over the six
     stable files the model's source_meta lines are cross-checked and agree.

Usage: python consumer_nix.py <fleet-dir> <bundle|wheel> <bundle-or-schema-dir>
Env: BFREE_REQUIRED=1 asserts pydantree_sitter_grammar is genuinely unimportable.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if os.environ.get("BFREE_REQUIRED"):
    try:
        import pydantree_sitter_grammar  # noqa: F401
        print(json.dumps({"ok": False,
                          "error": "pydantree_sitter_grammar IS importable — B leaked"}))
        sys.exit(1)
    except ModuleNotFoundError:
        pass

from pydantree_sitter import Language, M, OutputModel, Span, capture, source_meta  # noqa: E402

FILES = tuple(os.environ.get("NIX_FLEET_FILES",
              "mypi-agent.nix pydantree.nix terminal-state.nix "
              "structured-agents-v2.nix fsdantic.nix nixvim.nix "
              "flora.nix").split())


class Binding(OutputModel):
    """Every `attrpath = expression;` binding anywhere in the file: the value
    expression's raw text + the anchor's source_meta line and span.

    NOTE on the anchor's ATTRPATH: it is NOT str-capturable — nix's attrpath
    node is structural (a chain of identifiers + dots), and Job 4 rejects
    capturing a non-text-yielding node as str (the Phase-8 "no raw text of
    any node" residual). The key becomes consumer-side context (the tree walk
    at the captured span resolves the full dotted path).

    NOTE on source_meta: over large multiline-string-heavy files the nix
    grammar's node start POINTS are unreliable (the ecosystem position bug —
    see the module docstring); the consumer cross-checks the source_meta
    lines and falls back to byte-offset lines where they disagree."""

    __match__ = M("source_code", ..., "binding")
    value: str = capture("expression")
    line: int = source_meta()
    span: Span = source_meta()

    model_config = {"arbitrary_types_allowed": True}


class List(OutputModel):
    """Every `[ ... ]` list literal anywhere: the repeated `element` field's
    raw texts (the field-mode list). Used for packages — the consumer checks
    the ancestor chain for a `packages =` binding (ancestor context is not
    expressible as a capture over nix's attrset nesting)."""

    __match__ = M("source_code", ..., "list_expression")
    element: list[str] = capture("element")
    line: int = source_meta()
    span: Span = source_meta()

    model_config = {"arbitrary_types_allowed": True}


def load_language():
    if MODE == "bundle":
        return Language.load_bundle(str(ARTIFACT))
    if MODE == "wheel":
        import tree_sitter_nix
        schema = ARTIFACT / "node-schema.json"
        return Language.load(tree_sitter_nix.language(), schema=str(schema))
    raise SystemExit(f"unknown mode: {MODE}")


def line_at(src: bytes, byte: int) -> int:
    """1-based line from a byte offset (BYTE-based — immune to the nix
    grammar's position-point corruption)."""
    return src[:byte].count(b"\n") + 1


def dotted_path(node, src: bytes) -> str:
    """The FULL dotted path of a binding: the local attrpath raw text plus
    the attrpaths of ancestor bindings (walking the attrset nesting up to
    the top). `venv.enable` inside languages.python becomes
    `languages.python.venv.enable`; a `"quoted"` string attr keeps its
    quotes. A single top-level `config = { ... }` wrapper (the nixvim/flora
    module-output convention) is stripped — devenv option paths don't include
    the module wrapper."""
    n = node if node.type == "binding" else node.parent
    parts = []
    while n is not None:
        if n.type == "binding":
            for i in range(n.child_count):
                c = n.children[i]
                if n.field_name_for_child(i) == "attrpath":
                    parts.append(src[c.start_byte:c.end_byte].decode())
        n = n.parent
    path = ".".join(reversed(parts))
    return path[7:] if path.startswith("config.") else path


def walk_bindings(root):
    """All binding nodes in document order (BYTE-safe reads only — never
    touches start_point/range, which the nix grammar corrupts on large
    files)."""
    out = []

    def go(n):
        if n.type == "binding":
            out.append(n)
        for c in n.children:
            go(c)

    go(root)
    return out


def walk_lists(root):
    out = []

    def go(n):
        if n.type == "list_expression":
            out.append(n)
        for c in n.children:
            go(c)

    go(root)
    return out


def binding_value(node, src: bytes) -> str:
    for i in range(node.child_count):
        c = node.children[i]
        if node.field_name_for_child(i) == "expression":
            return src[c.start_byte:c.end_byte].decode()
    return ""


def binding_path(node, src: bytes) -> str:
    return dotted_path(node, src)


def is_packages_list(node, src: bytes) -> bool:
    n = node.parent
    while n is not None:
        if n.type == "binding" and binding_path(n, src) == "packages":
            return True
        n = n.parent
    return False


def element_rows(node, src: bytes) -> list[dict]:
    """Per-element rows for a packages list: raw element text (the field-mode
    capture's payload) + the element's own line (BYTE-computed)."""
    out = []
    for i in range(node.child_count):
        c = node.children[i]
        if node.field_name_for_child(i) == "element":
            out.append({"name": src[c.start_byte:c.end_byte].decode(),
                        "line": line_at(src, c.start_byte)})
    return out


def classify(path: str, value: str):
    """The inventory row kind for a binding's full path + value text."""
    if path.count(".") == 1 and path.startswith("env."):
        return "env"
    if path.startswith("scripts.") and path.endswith(".exec"):
        return "script"
    if path.startswith("tasks.") and path.endswith(".exec"):
        return "task"
    if path.endswith(".enable") and value == "true":
        return "switch"
    if path == "enterShell":
        return "shell"
    if path == "enterTest":
        return "test"
    return None


def main() -> int:
    global FLEET, MODE, ARTIFACT
    FLEET = Path(sys.argv[1])
    MODE = sys.argv[2]
    ARTIFACT = Path(sys.argv[3])
    lang = load_language()
    Binding.validate_with(lang)
    List.validate_with(lang)

    out = {
        "ok": None,
        "mode": MODE,
        "pydantree_sitter_grammar_importable": _b_importable(),
        "schema_bound": lang.schema is not None,
        "schema_kinds": len(lang.schema.kinds()) if lang.schema else None,
        "files": {},
    }
    truth = json.loads((FLEET / "ground_truth.json").read_text())
    all_ok = True
    source_meta_agrees = True   # the cross-check over the six stable files
    for fname in FILES:
        repo = fname[:-4]
        src = (FLEET / fname).read_bytes()
        tree = lang.parse(src)

        model_rows = [r.model_dump() for r in Binding.extract_tree(tree)]
        # the document-order pairing: model rows <-> walk entries. The model
        # order is the query's document order; the walk is document order.
        bindings = walk_bindings(tree.root_node)
        assert len(model_rows) == len(bindings), \
            f"{fname}: {len(model_rows)} model rows vs {len(bindings)} bindings"

        rows = {"packages": [], "env": [], "scripts": [], "tasks": [],
                "switches": [], "enterShell": [], "enterTest": []}
        for model_row, node in zip(model_rows, bindings):
            value = model_row["value"]          # the A-surface payload
            assert binding_value(node, src) == value, fname  # pairing sanity
            path = binding_path(node, src)
            byte_line = line_at(src, node.start_byte)
            if model_row["line"] != byte_line:
                # the position corruption: source_meta disagrees with the
                # byte-computed line (flora). Real gap in the ecosystem; the
                # byte-computed line is the truth (see module docstring).
                source_meta_agrees = False
            kind = classify(path, value)
            if kind == "env":
                rows["env"].append({"repo": repo, "name": path,
                                    "value": value, "line": byte_line})
            elif kind == "script":
                rows["scripts"].append({"repo": repo, "name": path,
                                        "body": value, "line": byte_line})
            elif kind == "task":
                rows["tasks"].append({"repo": repo, "name": path,
                                      "body": value, "line": byte_line})
            elif kind == "switch":
                rows["switches"].append({"repo": repo, "path": path,
                                         "line": byte_line})
            elif kind == "shell":
                rows["enterShell"].append({"repo": repo, "kind": "enterShell",
                                           "body": value, "line": byte_line})
            elif kind == "test":
                rows["enterTest"].append({"repo": repo, "kind": "enterTest",
                                          "body": value, "line": byte_line})

        for lst in walk_lists(tree.root_node):
            if not is_packages_list(lst, src):
                continue
            for el in element_rows(lst, src):
                rows["packages"].append({"repo": repo, "name": el["name"],
                                         "line": el["line"]})

        out["files"][fname] = rows
        t = {k: [r for r in v if r["repo"] == repo]
             for k, v in truth.items() if isinstance(v, list)}
        ok = (rows["packages"] == t["packages"] and rows["env"] == t["env"]
              and rows["scripts"] == t["scripts"] and rows["tasks"] == t["tasks"]
              and rows["switches"] == t["switches"]
              and rows["enterShell"] == t["enterShell"]
              and rows["enterTest"] == t["enterTest"])
        all_ok = all_ok and ok
        if not ok:
            for k in rows:
                if rows[k] != t[k]:
                    print(f"  MISMATCH {fname}.{k}: got {len(rows[k])} "
                          f"want {len(t[k])}")
                    for g, w in zip(rows[k], t[k]):
                        if g != w:
                            print(f"    got  {g}")
                            print(f"    want {w}")
    out["ok"] = all_ok
    out["source_meta_agrees_with_byte_lines"] = source_meta_agrees
    print(json.dumps(out, indent=2))
    return 0 if all_ok else 1


def _b_importable() -> bool:
    try:
        import pydantree_sitter_grammar  # noqa: F401
        return True
    except ModuleNotFoundError:
        return False


if __name__ == "__main__":
    sys.exit(main())
