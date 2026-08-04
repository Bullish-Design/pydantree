#!/usr/bin/env python3
"""devenv-extract — the devenv fleet inventory with pydantree.

A copyable end-to-end for **Product A** (tsquery) over the REAL
tree-sitter-nix grammar (nix-community, v0.3.0 source here; the PyPI wheel
tree-sitter-nix 0.1.0 for the fresh-venv shape) — a grammar we don't own and
never authored. The corpus is a subset of the author's OWN real `devenv.nix`
configs (7 repos, 8-526 lines), and the extraction task is the **fleet
inventory**: packages, env vars, scripts, tasks, enabled switches,
enterShell/enterTest — typed rows, aggregated per repo, with the schema
checks active BEFORE any text is parsed.

Usage (the "hundreds of grammars" shape — light wheels + a community wheel):

    uv venv --python 3.13 .venv
    uv pip install --python .venv/bin/python \
        pydantree-tscore pydantree-tsquery tree-sitter-nix
    .venv/bin/python extract.py

(Or, over a pydantree bundle: `python extract.py --bundle <bundle-dir>`.)

The models below are the whole query: each `__match__` ancestor path plus
the captures declare both the pattern and the output type. The schema
(`node-schema.json`, derived from the grammar source v0.3.0) is bound to the
language so `validate_with` runs the model↔grammar and capture↔type checks
before parsing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FLEET = HERE / "fleet"

from tsquery import Language, M, OutputModel, Span, capture, source_meta  # noqa: E402

FILES = ("mypi-agent.nix", "pydantree.nix", "terminal-state.nix",
         "structured-agents-v2.nix", "fsdantic.nix", "nixvim.nix")


class Binding(OutputModel):
    """Every `attrpath = expression;` binding anywhere in the file: the value
    expression's raw text + the anchor's source_meta line and span.

    The binding's ATTRPATH is NOT str-capturable — nix's attrpath node is
    structural (a chain of identifiers + dots), and the schema checks reject
    capturing a non-text-yielding node as str (the "no raw text of any node"
    residual). The key becomes a small consumer-side walk (see dotted_path).

    Line numbers: the nix grammar has an ecosystem position bug (tree-sitter
    0.26 + this grammar's scanner) — node start POINTS on large
    multiline-string-heavy files (flora) are unreliable or crash; start
    BYTES and node texts are reliable. The example computes every line from
    the byte offset and cross-checks the source_meta lines on the stable
    files (see the README's "Position caveat")."""

    __match__ = M("source_code", ..., "binding")
    value: str = capture("expression")
    line: int = source_meta()
    span: Span = source_meta()

    model_config = {"arbitrary_types_allowed": True}


class List(OutputModel):
    """Every `[ ... ]` list literal anywhere: the repeated `element` field's
    raw texts (the field-mode list). Packages lists are the ones whose
    ancestor chain has a bare `packages =` binding (a consumer-side check —
    ancestor context is not expressible as a capture over attrset nesting)."""

    __match__ = M("source_code", ..., "list_expression")
    element: list[str] = capture("element")
    line: int = source_meta()
    span: Span = source_meta()

    model_config = {"arbitrary_types_allowed": True}


# -- context helpers (the honest escape hatches; see the README) ------------

def line_at(src: bytes, byte: int) -> int:
    """1-based line from a byte offset (BYTE-based — immune to the nix
    grammar's position-point corruption)."""
    return src[:byte].count(b"\n") + 1


def dotted_path(node, src: bytes) -> str:
    """The FULL dotted path of a binding (attrset nesting reconstructed by
    walking ancestor bindings). A single top-level `config = { ... }` wrapper
    (the nixvim/flora module convention) is stripped — devenv option paths
    don't include it."""
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


def walk(root, kind: str):
    out = []

    def go(n):
        if n.type == kind:
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


def is_packages_list(node, src: bytes) -> bool:
    n = node.parent
    while n is not None:
        if n.type == "binding" and dotted_path(n, src) == "packages":
            return True
        n = n.parent
    return False


def element_rows(node, src: bytes) -> list[dict]:
    out = []
    for i in range(node.child_count):
        c = node.children[i]
        if node.field_name_for_child(i) == "element":
            out.append({"name": src[c.start_byte:c.end_byte].decode(),
                        "line": line_at(src, c.start_byte)})
    return out


def classify(path: str, value: str):
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


def load_language() -> Language:
    """Default: the wheel shape — tree_sitter_nix.language() (a bare
    PyCapsule from this wheel — tsquery converts it) with the derived schema
    bound explicitly (the schema ships in this dir). With `--bundle <dir>`:
    the one-line bundle shape."""
    if "--bundle" in sys.argv:
        return Language.load_bundle(sys.argv[sys.argv.index("--bundle") + 1])
    import tree_sitter_nix
    return Language.load(tree_sitter_nix.language(),
                         schema=str(HERE / "node-schema.json"))


def main() -> int:
    lang = load_language()
    # the checks run BEFORE any text is parsed
    for model in (Binding, List):
        model.validate_with(lang)

    print(f"schema: {len(lang.schema.kinds())} kinds · checks active\n")
    inventory = {"packages": [], "env": [], "scripts": [], "tasks": [],
                 "switches": [], "enterShell": [], "enterTest": []}
    for fname in FILES:
        repo = fname[:-4]
        src = (FLEET / fname).read_bytes()
        tree = lang.parse(src)

        model_rows = [r.model_dump() for r in Binding.extract_tree(tree)]
        bindings = walk(tree.root_node, "binding")
        assert len(model_rows) == len(bindings), fname

        print(f"── {repo} ({len(src.splitlines())} lines) ──")
        for model_row, node in zip(model_rows, bindings):
            value = model_row["value"]
            path = dotted_path(node, src)
            line = line_at(src, node.start_byte)
            kind = classify(path, value)
            if kind == "env":
                inventory["env"].append({"repo": repo, "name": path,
                                         "value": value, "line": line})
                print(f"  env       {path} = {value[:48]!r} (line {line})")
            elif kind == "script":
                inventory["scripts"].append({"repo": repo, "name": path,
                                             "body": value, "line": line})
                print(f"  script    {path} ({len(value)} chars, line {line})")
            elif kind == "task":
                inventory["tasks"].append({"repo": repo, "name": path,
                                           "body": value, "line": line})
                print(f"  task      {path} ({len(value)} chars, line {line})")
            elif kind == "switch":
                inventory["switches"].append({"repo": repo, "path": path,
                                              "line": line})
                print(f"  switch    {path} (line {line})")
            elif kind == "shell":
                inventory["enterShell"].append({"repo": repo, "kind": "enterShell",
                                                "body": value, "line": line})
                print(f"  shell     enterShell ({len(value)} chars, line {line})")
            elif kind == "test":
                inventory["enterTest"].append({"repo": repo, "kind": "enterTest",
                                               "body": value, "line": line})
                print(f"  shell     enterTest ({len(value)} chars, line {line})")

        for lst in walk(tree.root_node, "list_expression"):
            if not is_packages_list(lst, src):
                continue
            for el in element_rows(lst, src):
                inventory["packages"].append({"repo": repo, "name": el["name"],
                                              "line": el["line"]})
                print(f"  package   {el['name']} (line {el['line']})")
        print()

    # self-check: the rows must match the hand-written ground truth
    truth = json.loads((FLEET / "ground_truth.json").read_text())
    ok = True
    for key in ("packages", "env", "scripts", "tasks", "switches",
                "enterShell", "enterTest"):
        if inventory[key] != truth[key]:
            ok = False
            print(f"  MISMATCH {key}: got {len(inventory[key])} "
                  f"want {len(want)}")
    total = sum(len(v) for v in inventory.values())
    print(f"{total} rows extracted — "
          + ("all match the hand-written ground truth ✓" if ok
             else "mismatch (see above) ✗"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
