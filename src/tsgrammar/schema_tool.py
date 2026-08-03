"""tsgrammar.schema_tool — the community-schema path (CONCEPT §7, Phase 5/6).

The "community grammar ships no schema" problem: a wheel (tree-sitter-json,
tree-sitter-rust, ...) does not ship node-types.json, and A's checks need a
node-schema. The fix is one command over the grammar SOURCE:

    grammar dir with grammar.json
        -> `tree-sitter generate` (the CLI writes src/node-types.json)
        -> derive_from_node_types -> node-schema.json

The tool runs the CLI (build-time, B-side); the OUTPUT (node-schema.json) is
consumed B-free by A, exactly like a B-built bundle's schema. Over a
tsgrammar IR the derived schema is equivalent to derive_from_ir's on the
shared subset (the Phase-4 agreement check — the CLI byproduct is what
derive_from_ir mirrors).

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

from tscore.schema import NodeSchema, derive_from_node_types


# the loader shim shipped inside a packaged bundle (same as tsgrammar.pipeline)
_BUNDLE_LOADER_SOURCE = '''\
"""Load this bundle's grammar into a tree_sitter.Language (B-free)."""
from pathlib import Path
from tscore.loader import load_bundle


def language():
    return load_bundle(Path(__file__).resolve().parent).language
'''


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
    for cand in (dst / "scanner.c", work / "scanner.c"):
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
    grammar_json, _scanner = _resolve_grammar_json(grammar_dir), None

    work = Path(workdir) if workdir is not None \
        else Path(tempfile.mkdtemp(prefix="tsgrammar-community-"))
    work.mkdir(parents=True, exist_ok=True)
    # copy the grammar sources in (never touch the author's checkout) and run
    # the CLI with an explicit output dir so the byproduct location is
    # layout-independent (grammar.json at root vs src/grammar.json)
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
    if not keep:
        shutil.rmtree(work)
    return schema


def build_community_bundle(grammar_dir: Path | str, out: Path | str, *,
                           name: str | None = None,
                           workdir: Path | None = None,
                           keep: bool = False) -> Path:
    """Phase 6 (Run 2): a REAL community grammar source -> a shippable bundle,
    the same 4-file layout B's own pipeline produces:

        grammar.so        compiled from the source (parser.c + scanner.c)
        node-schema.json  derived from the CLI's fresh node-types.json
        tree-sitter.json  bundle metadata (name = the .so export symbol)
        loader.py         the B-free shim over tscore.loader

    Consumed B-free with `Language.load_bundle(dir)` — the community path
    end to end over a grammar we don't own. Returns the bundle dir.
    """
    from .pipeline import compile_parser
    grammar_dir = Path(grammar_dir)
    out = Path(out)
    work = Path(workdir) if workdir is not None \
        else Path(tempfile.mkdtemp(prefix="tsgrammar-community-build-"))
    work.mkdir(parents=True, exist_ok=True)

    grammar_json, scanner = _copy_grammar_source(grammar_dir, work)
    gen_out = work / "gen"
    grammar_name = name or _grammar_name(grammar_dir, grammar_json.parent)

    gen = subprocess.run(
        ["tree-sitter", "generate", str(grammar_json.relative_to(work)),
         "-o", str(gen_out)],
        capture_output=True, text=True, cwd=str(work), check=False)
    if gen.returncode != 0:
        raise RuntimeError(
            f"tree-sitter generate failed for {grammar_dir}: "
            f"{gen.stderr or gen.stdout}")
    parser_c = gen_out / "parser.c"
    if not parser_c.exists():
        raise RuntimeError(
            f"generate exited 0 but wrote no parser.c in {gen_out}")
    so_path = work / f"{grammar_name}.so"
    cc = compile_parser(gen_out, so_path,
                        scanner=scanner if scanner is not None else None)
    if cc.returncode != 0:
        raise RuntimeError(
            f"gcc failed compiling {grammar_dir} (exit {cc.returncode}):\n"
            f"{cc.stderr}")

    node_types = gen_out / "node-types.json"
    if not node_types.exists():
        raise RuntimeError(f"generate wrote no node-types.json in {gen_out}")
    schema = NodeSchema.from_list(derive_from_node_types(node_types), name=grammar_name)

    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(so_path, out / "grammar.so")
    schema.write(out / "node-schema.json")
    (out / "tree-sitter.json").write_text(json.dumps({
        "name": grammar_name,
        "artifact": "grammar.so",
        "schema": "node-schema.json",
        "abi": "15",
        "toolchain": "community",
    }, indent=2))
    (out / "loader.py").write_text(_BUNDLE_LOADER_SOURCE)
    if not keep:
        shutil.rmtree(work)
    return out


def _grammar_name(grammar_dir: Path, src_dir: Path) -> str:
    """The grammar name from tree-sitter.json metadata, else the dir name."""
    cfg = grammar_dir / "tree-sitter.json"
    if cfg.exists():
        try:
            meta = json.loads(cfg.read_text())
            grammars = meta.get("grammars") or []
            if grammars:
                return grammars[0].get("name") or src_dir.name
        except ValueError:
            pass
    return src_dir.name


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
