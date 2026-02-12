from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantree.codegen.common import CodegenDiagnosticError, read_model, write_model
from pydantree.codegen.emit import EmitOutput, emit_models
from pydantree.codegen.ingest import IngestOutput, ingest_scm
from pydantree.codegen.manifest import build_manifest
from pydantree.codegen.normalize import NormalizeOutput, normalize_ingested
from pydantree.registry import WorkshopLayout, resolve_repository_root


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not getattr(args, "command", None):
        parser.print_help(sys.stderr)
        raise SystemExit(2)

    try:
        _dispatch(args)
    except CodegenDiagnosticError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pydantree-codegen", description="Pydantree code generation pipeline")
    subparsers = parser.add_subparsers(dest="command")

    ingest = subparsers.add_parser("ingest", help="Discover .scm files and collect provenance")
    ingest.add_argument("language")
    ingest.add_argument("query_pack")
    ingest.add_argument("--out", type=Path)
    ingest.add_argument("--pattern", default="*.scm")

    normalize = subparsers.add_parser("normalize", help="Normalize ingested data into stable pattern IDs")
    normalize.add_argument("language")
    normalize.add_argument("query_pack")
    normalize.add_argument("--input", type=Path, dest="input_path")
    normalize.add_argument("--out", type=Path)

    emit = subparsers.add_parser("emit", help="Generate deterministic Pydantic model modules")
    emit.add_argument("language")
    emit.add_argument("query_pack")
    emit.add_argument("--input", type=Path, dest="input_path")
    emit.add_argument("--output-dir", type=Path)
    emit.add_argument("--out", type=Path)

    manifest = subparsers.add_parser("manifest", help="Build reproducibility metadata from stage artifacts")
    manifest.add_argument("language")
    manifest.add_argument("query_pack")
    manifest.add_argument("--ingest", type=Path, dest="ingest_path")
    manifest.add_argument("--normalize", type=Path, dest="normalize_path")
    manifest.add_argument("--emit", type=Path, dest="emit_path")
    manifest.add_argument("--out", type=Path)

    return parser


def _layout() -> WorkshopLayout:
    return WorkshopLayout.from_path(resolve_repository_root())


def _dispatch(args: argparse.Namespace) -> None:
    layout = _layout()

    if args.command == "ingest":
        root_dir = layout.queries_pack_dir(language=args.language, query_pack=args.query_pack)
        out = args.out or (layout.repository_root / "build" / f"ingest.{args.language}.{args.query_pack}.json")
        payload = ingest_scm(root_dir=root_dir, pattern=args.pattern)
        write_model(out, payload)
        print(f"Wrote ingest artifact: {out}")
        return

    if args.command == "normalize":
        input_path = args.input_path or (layout.repository_root / "build" / f"ingest.{args.language}.{args.query_pack}.json")
        out = args.out or layout.ir_file(language=args.language, query_pack=args.query_pack)
        ingest = IngestOutput.model_validate(read_model(input_path, IngestOutput))
        normalized = normalize_ingested(ingest)
        write_model(out, normalized)
        print(f"Wrote normalize artifact: {out}")
        return

    if args.command == "emit":
        input_path = args.input_path or layout.ir_file(language=args.language, query_pack=args.query_pack)
        output_dir = args.output_dir or layout.generated_models_dir(language=args.language, query_pack=args.query_pack)
        out = args.out or (layout.repository_root / "build" / f"emit.{args.language}.{args.query_pack}.json")
        normalize = NormalizeOutput.model_validate(read_model(input_path, NormalizeOutput))
        emitted = emit_models(normalize, output_dir=output_dir)
        write_model(out, emitted)
        print(f"Wrote emit artifact: {out}")
        return

    if args.command == "manifest":
        ingest_path = args.ingest_path or (layout.repository_root / "build" / f"ingest.{args.language}.{args.query_pack}.json")
        normalize_path = args.normalize_path or layout.ir_file(language=args.language, query_pack=args.query_pack)
        emit_path = args.emit_path or (layout.repository_root / "build" / f"emit.{args.language}.{args.query_pack}.json")
        out = args.out or layout.manifest_file(language=args.language, query_pack=args.query_pack)
        ingest = IngestOutput.model_validate(read_model(ingest_path, IngestOutput))
        normalize = NormalizeOutput.model_validate(read_model(normalize_path, NormalizeOutput))
        emit = EmitOutput.model_validate(read_model(emit_path, EmitOutput))
        manifest = build_manifest(ingest=ingest, normalize=normalize, emit=emit)
        write_model(out, manifest)
        print(f"Wrote manifest artifact: {out}")
        return

    raise CodegenDiagnosticError("cli", f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
