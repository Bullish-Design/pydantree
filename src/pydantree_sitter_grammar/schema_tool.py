"""pydantree_sitter_grammar.schema_tool — the community-schema path (CONCEPT §7, Phase 5/6).

The "community grammar ships no schema" problem: a wheel (tree-sitter-json,
tree-sitter-rust, ...) does not ship node-types.json, and A's checks need a
node-schema. The fix is one command over the grammar SOURCE:

    grammar dir with grammar.json
        -> `tree-sitter generate` (the CLI writes src/node-types.json)
        -> derive_from_node_types -> node-schema.json

The tool runs the CLI (build-time, B-side); the OUTPUT (node-schema.json) is
consumed B-free by A, exactly like a B-built bundle's schema. Post-014 (D3)
this is the ONLY derivation: the schema IS the CLI byproduct — a B-built
bundle's node-schema.json is the generate run's node-types.json copied
byte-for-byte.

Phase 6: the tool now accepts REAL community grammar source layouts — a
repo checkout with `src/grammar.json` (the standard tree-sitter layout,
e.g. tree-sitter-rust) — and gains `build_community_bundle`: source ->
compiled grammar.so + node-schema.json + metadata + loader, the same
4-file bundle B's own pipeline produces, ready for B-free consumption.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pydantree_sitter.schema import NodeSchema, derive_from_node_types


def _resolve_grammar_json(grammar_dir: Path) -> Path:
    """The grammar.json in a source dir: `<dir>/grammar.json` (B's own emitted
    layout) or `<dir>/src/grammar.json` (the standard community repo layout)."""
    for cand in (grammar_dir / "grammar.json", grammar_dir / "src" / "grammar.json"):
        if cand.exists():
            return cand
    raise FileNotFoundError(
        f"not a grammar source dir: {grammar_dir} (no grammar.json or "
        f"src/grammar.json)")


def _copy_grammar_source(grammar_dir: Path, work: Path):
    """Copy a grammar source dir into `work` (never touch the author's
    checkout): the grammar.json's own dir (src/ for community repos) plus a
    top-level tree-sitter.json when present. Returns (grammar_json_rel,
    scanner_path_or_None) — the grammar.json path relative to work (the CLI
    arg) and the external scanner if the source ships one."""
    grammar_json = _resolve_grammar_json(grammar_dir)
    src = grammar_json.parent
    dst = work / src.name
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copyfile(src, dst)
    cfg = grammar_dir / "tree-sitter.json"
    if cfg.exists():
        shutil.copyfile(cfg, work / "tree-sitter.json")
    rel = dst / "grammar.json"
    scanner = None
    for cand in (dst / "scanner.c", dst / "scanner.cc",
                 work / "scanner.c", work / "scanner.cc"):
        if cand.exists():
            scanner = cand
            break
    return rel, scanner


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

    work = Path(workdir) if workdir is not None \
        else Path(tempfile.mkdtemp(prefix="pydantree_sitter_grammar-community-"))
    work.mkdir(parents=True, exist_ok=True)
    # copy the grammar sources in (never touch the author's checkout) and run
    # the CLI with an explicit output dir so the byproduct location is
    # layout-independent (grammar.json at root vs src/grammar.json)
    try:
        grammar_json, _scanner = _copy_grammar_source(grammar_dir, work)
        gen_out = work / "gen"

        proc = subprocess.run(
            ["tree-sitter", "generate", str(grammar_json.relative_to(work)),
             "-o", str(gen_out)],
            capture_output=True, text=True, cwd=str(work), check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"tree-sitter generate failed for {grammar_dir}: "
                f"{proc.stderr or proc.stdout}")

        node_types = gen_out / "node-types.json"
        if not node_types.exists():
            raise RuntimeError(
                f"generate succeeded but wrote no node-types.json in {gen_out}")
        schema = NodeSchema.from_list(derive_from_node_types(node_types), name=name)
        out_path = Path(out) if out is not None else work / "node-schema.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        schema.write(out_path)
        return schema
    finally:
        # REVIEW 020 minor: a failed generate used to leave the workdir
        # behind (only the success path removed it).
        if not keep:
            shutil.rmtree(work, ignore_errors=True)


def build_community_bundle(grammar_dir: Path | str, out: Path | str, *,
                           name: str | None = None) -> Path:
    """Phase 6 (Run 2): a REAL community grammar source -> a shippable
    bundle, the same 4-file layout B's own pipeline produces (D10: this
    delegates to the pipeline's `build_from_source_dir` + the ONE bundle
    writer — same cache, same errors, same writer; the schema IS the CLI
    byproduct by construction, D3). The pipeline owns the build
    (content-addressed cache), so there is no workdir/keep (B22).

        grammar.so        compiled from the source (parser.c + scanner.c)
        node-schema.json  the generate run's node-types.json byproduct
        tree-sitter.json  bundle metadata (name = the .so export symbol)
        loader.py         the B-free shim over pydantree_sitter.loader

    Consumed B-free with `Language.load_bundle(dir)`. Returns the bundle dir.
    """
    from .pipeline import build_from_source_dir, write_bundle
    result = build_from_source_dir(grammar_dir, name=name)
    return write_bundle(result, out)


def main(argv: list[str] | None = None) -> int:
    """CLI: `python -m pydantree_sitter_grammar.schema_tool <grammar-dir> [-o out.json]
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
    schema = derive_schema_for_dir(args[0], name=name, out=out)
    print(f"wrote {out} ({len(schema.node_types)} kinds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
