"""tsgrammar.schema_tool — the community-schema path (CONCEPT §7, Phase 5).

The "community grammar ships no schema" problem: a wheel (tree-sitter-json,
tree-sitter-python, ...) does not ship node-types.json, and A's checks need a
node-schema. The fix is one command over the grammar SOURCE:

    grammar dir with grammar.json
        -> `tree-sitter generate` (the CLI writes src/node-types.json)
        -> derive_from_node_types -> node-schema.json

The tool runs the CLI (build-time, B-side); the OUTPUT (node-schema.json) is
consumed B-free by A, exactly like a B-built bundle's schema. Over a
tsgrammar IR the derived schema is equivalent to derive_from_ir's on the
shared subset (the Phase-4 agreement check — the CLI byproduct is what
derive_from_ir mirrors).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tscore.schema import NodeSchema, derive_from_node_types


def derive_schema_for_dir(grammar_dir: Path | str, *,
                          name: str | None = None,
                          workdir: Path | None = None,
                          out: Path | str | None = None,
                          keep: bool = False) -> NodeSchema:
    """Run the CLI generate in `grammar_dir` (which must contain a
    grammar.json) and derive the node-schema from the produced
    node-types.json. Returns the NodeSchema and writes node-schema.json to
    `out` (default: the workdir root).

    `workdir` may be given to control where the CLI runs (default: a temp
    dir). The grammar_dir is copied into the workdir so the CLI's cwd-based
    output never pollutes the source checkout. The workdir is removed after
    the run unless `keep=True` — pass `out=` to persist the schema.
    """
    grammar_dir = Path(grammar_dir)
    if not (grammar_dir / "grammar.json").exists():
        raise FileNotFoundError(
            f"not a grammar source dir: {grammar_dir} (no grammar.json)")

    work = Path(workdir) if workdir is not None \
        else Path(tempfile.mkdtemp(prefix="tsgrammar-community-"))
    work.mkdir(parents=True, exist_ok=True)
    # copy the grammar sources in (the CLI writes src/node-types.json next to
    # the grammar.json; never touch the author's checkout)
    for src in grammar_dir.iterdir():
        dst = work / src.name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copyfile(src, dst)

    proc = subprocess.run(
        ["tree-sitter", "generate", "grammar.json"],
        capture_output=True, text=True, cwd=str(work), check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"tree-sitter generate failed for {grammar_dir}: "
            f"{proc.stderr or proc.stdout}")

    node_types = work / "src" / "node-types.json"
    if not node_types.exists():
        raise RuntimeError(
            f"generate succeeded but wrote no node-types.json in {work / 'src'}")
    schema = NodeSchema.from_list(derive_from_node_types(node_types), name=name)
    out_path = Path(out) if out is not None else work / "node-schema.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    schema.write(out_path)
    if not keep:
        shutil.rmtree(work)
    return schema


def main(argv: list[str] | None = None) -> int:
    """CLI: `python -m tsgrammar.schema_tool <grammar-dir> [-o out.json]
    [-n name]` — emit node-schema.json for a grammar source dir."""
    argv = list(sys.argv[1:] if argv is None else argv)
    out = "node-schema.json"
    name = None
    args: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "-o" and i + 1 < len(argv):
            out = argv[i + 1]
            i += 2
        elif argv[i] == "-n" and i + 1 < len(argv):
            name = argv[i + 1]
            i += 2
        else:
            args.append(argv[i])
            i += 1
    if not args:
        print(__doc__)
        return 2
    schema = derive_schema_for_dir(args[0], name=name, keep=True)
    Path(out).write_text(schema.to_json())
    print(f"wrote {out} ({len(schema.node_types)} kinds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
