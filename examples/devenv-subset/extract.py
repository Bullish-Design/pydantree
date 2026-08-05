#!/usr/bin/env python3
"""devenv-subset — BOTH halves of pydantree, end to end.

Product B (pydantree_sitter_grammar) authors a small "devenv config surface" grammar
(grammar.py + scanner.c), builds it into a bundle. Product A (pydantree_sitter)
consumes the bundle: the fleet inventory over real sanitized devenv.nix
configs as typed rows, with record mode working over the authored pair shape.

Run it (the dev venv has BOTH halves — B's toolchain is a build-time thing):

    devenv shell -- python examples/devenv-subset/extract.py

The bundle lands in dist/devenv-bundle — copy that directory and a node-schema
next to a consumer for the B-free shape (README).

Why the authored shape matters (the Phase-9 findings this example resolves):
  * the attrset pair is a direct child KIND with key/value FIELDS — record
    mode's pair-kind detection accepts it (upstream nix's binding_set/
    binding/attrpath shape raises UnsupportedShapeError);
  * the key is ONE token — `key: str = capture("key")` passes the schema
    checks (upstream nix's structural attrpath is rejected);
  * the external scanner is ~40 lines and position-stable — source_meta
    lines are correct with no byte-offset workaround (upstream's scanner
    corrupts node start-points on large files).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = Path(os.environ.get("DEVENV_BUNDLE_DIR",
                           str(HERE.parent.parent / "dist" / "devenv-bundle")))
FIXTURES = HERE / "fixtures"

FILES = ("mypi-agent.nix", "pydantree.nix", "terminal-state.nix",
         "structured-agents-v2.nix")


# --------------------------------------------------------------------------
# Product B — build the grammar + scanner into a bundle
# --------------------------------------------------------------------------

def build_bundle() -> Path:
    sys.path.insert(0, str(HERE))
    from grammar import build
    import pydantree_sitter_grammar as tg

    g = build()
    warnings = list(tg.run_checks(g))
    assert not tg.errors(g), warnings
    result = tg.build_builder(g, scanner=str(HERE / "scanner.c"))
    bundle = result.package(DIST)
    return bundle


# --------------------------------------------------------------------------
# Product A — the models (the A surface over the bundle)
# --------------------------------------------------------------------------

from pydantree_sitter import (  # noqa: E402
    Language, M, OutputModel, Span, capture, propose_value_map, source_meta,
)


class Pair(OutputModel):
    """Every `key = value;` pair: the KEY is a capture (the authored token —
    the phase-9 finding that nix's attrpath is not str-capturable is gone),
    the value is the raw expression text, and source_meta gives the line."""

    __match__ = M("source_file", ..., "pair")
    key: str = capture("key")
    value: str = capture("value")
    line: int = source_meta()
    span: Span = source_meta()

    model_config = {"arbitrary_types_allowed": True}


class ListLiteral(OutputModel):
    """Every `[ ... ]` list literal: the repeated `element` field as a
    field-mode list (raw element texts). Packages lists are the ones whose
    ancestor pair is a `packages` key — ancestor context, resolved by a walk."""

    __match__ = M("source_file", ..., "list")
    element: list[str] = capture("element")
    line: int = source_meta()
    span: Span = source_meta()

    model_config = {"arbitrary_types_allowed": True}


class EnvRecord(OutputModel):
    """Record mode over the nested `env = { ... }` attrset. The authored
    pair shape (a child kind with key/value fields) is what record mode's
    pair-kind detection needs — the Phase-9 probe's UnsupportedShapeError
    is gone. A REQUIRED field filters the record: only attrsets with a GREET
    key materialize (the env attrset; others drop out)."""

    __match__ = M("source_file", ..., "attrset", record=True)
    GREET: str
    TMUX_TMPDIR: str | None = None
    line: int = source_meta()


class Toolchain(OutputModel):
    """Record mode over every `{ enable = ...; ... }` attrset — the "what's
    switched on" containers across the fleet. Optional `version` shows the
    shape variety (python toolchains have it; the uv/sync containers don't)."""

    __match__ = M("source_file", ..., "attrset", record=True)
    enable: str
    version: str | None = None
    line: int = source_meta()


# -- context helpers (the honest escape hatch: full dotted paths are the
#    ancestor nesting, which is context, not a capture) ----------------------

def node_at(tree, span: Span):
    s, e = span.start_byte, span.end_byte
    target = None

    def walk(n):
        nonlocal target
        if target is not None:
            return
        a, b = n.byte_range
        if a == s and b == e:
            target = n
            return
        for c in n.children:
            walk(c)

    walk(tree.root_node)
    return target


def dotted_path(node, src: bytes) -> str:
    """The FULL dotted path of a pair: the local key token + the key tokens
    of ancestor pairs (the attrset nesting). `enable` inside `python = {...}`
    inside `languages = {...}` becomes `languages.python.enable`."""
    n = node if node.type == "pair" else node.parent
    parts = []
    while n is not None:
        if n.type == "pair":
            for i in range(n.child_count):
                c = n.children[i]
                if n.field_name_for_child(i) == "key":
                    parts.append(src[c.start_byte:c.end_byte].decode())
        n = n.parent
    return ".".join(reversed(parts))


def is_packages_list(node, src: bytes) -> bool:
    n = node.parent
    while n is not None:
        if n.type == "pair" and dotted_path(n, src) == "packages":
            return True
        n = n.parent
    return False


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


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def main() -> int:
    print("== Product B: author + build ==")
    print(f"   grammar.py + scanner.c -> {DIST}")
    bundle = build_bundle()
    print("   bundle:", sorted(p.name for p in bundle.iterdir()))

    lang = Language.load_bundle(bundle)
    # the authored grammar is not the JSON family — value shapes are
    # declared data (D6): take the reviewed DRAFT map from the schema (this
    # example commits the draft; a real bundle would ship a reviewed one)
    if lang.schema is not None:
        lang = Language.load_bundle(bundle,
                                    value_map=propose_value_map(lang.schema))
    for model in (Pair, ListLiteral):
        model.validate_with(lang)
    # record models bind through the Language (they need the value map)
    env_ext = lang.extractor(EnvRecord, strict=False)
    tool_ext = lang.extractor(Toolchain, strict=False)
    print(f"   checks active · schema: {len(lang.schema.kinds())} kinds\n")

    print("== Product A: the fleet inventory (typed rows) ==")
    inventory = {"packages": [], "env": [], "scripts": [], "tasks": [],
                 "switches": [], "enterShell": [], "enterTest": []}
    env_records, toolchain_records = [], []
    for fname in FILES:
        repo = fname[:-4]
        src = (FIXTURES / fname).read_bytes()
        tree = lang.parse(src)

        pairs = [r.model_dump() for r in Pair.extract_tree(tree)]
        pair_nodes = []
        for r in pairs:
            n = node_at(tree, r["span"])
            assert n is not None and n.type == "pair", fname
            pair_nodes.append(n)

        print(f"── {repo} ({len(src.splitlines())} lines) ──")
        for row, node in zip(pairs, pair_nodes):
            value, path = row["value"], dotted_path(node, src)
            line = row["line"]
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
                inventory["enterShell"].append(
                    {"repo": repo, "kind": "enterShell", "body": value,
                     "line": line})
                print(f"  shell     enterShell ({len(value)} chars, line {line})")
            elif kind == "test":
                inventory["enterTest"].append(
                    {"repo": repo, "kind": "enterTest", "body": value,
                     "line": line})
                print(f"  shell     enterTest ({len(value)} chars, line {line})")

        for lst_row in [r.model_dump() for r in ListLiteral.extract_tree(tree)]:
            node = node_at(tree, lst_row["span"])
            if not is_packages_list(node, src):
                continue
            for i in range(node.child_count):
                c = node.children[i]
                if node.field_name_for_child(i) == "element":
                    inventory["packages"].append(
                        {"repo": repo,
                         "name": src[c.start_byte:c.end_byte].decode(),
                         "line": c.start_point.row + 1})
                    print(f"  package   {inventory['packages'][-1]['name']} "
                          f"(line {inventory['packages'][-1]['line']})")

        for r in [x.model_dump() for x in env_ext.extract_tree(tree)]:
            r["repo"] = repo
            env_records.append(r)
        for r in [x.model_dump() for x in tool_ext.extract_tree(tree)]:
            r["repo"] = repo
            toolchain_records.append(r)
        print()

    print("== record mode over the authored pair shape ==")
    for r in env_records:
        print(f"  env record     {r['repo']}:{r['line']}  GREET={r['GREET']}"
              + (f", TMUX_TMPDIR={r['TMUX_TMPDIR']}" if r["TMUX_TMPDIR"] else ""))
    for r in toolchain_records:
        v = f", version={r['version']}" if r["version"] else ""
        print(f"  toolchain      {r['repo']}:{r['line']}  enable={r['enable']}{v}")
    print()

    # self-check vs the hand-written ground truth
    truth = json.loads((HERE / "ground_truth.json").read_text())
    ok = True
    checks = {"packages": inventory["packages"], "env": inventory["env"],
              "scripts": inventory["scripts"], "tasks": inventory["tasks"],
              "switches": inventory["switches"],
              "enterShell": inventory["enterShell"],
              "enterTest": inventory["enterTest"],
              "env_records": env_records,
              "toolchain_records": toolchain_records}
    for key, got in checks.items():
        if got != truth[key]:
            ok = False
            print(f"  MISMATCH {key}: got {len(got)} want {len(truth[key])}")
    total = sum(len(v) for v in checks.values())
    print(f"{total} rows extracted — "
          + ("all match the hand-written ground truth ✓" if ok
             else "mismatch (see above) ✗"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
