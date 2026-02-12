from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import uuid4

from pydantree.codegen.common import CodegenDiagnosticError, read_model, write_model
from pydantree.codegen.emit import EmitOutput, emit_models
from pydantree.codegen.ingest import IngestOutput, ingest_scm
from pydantree.codegen.manifest import build_manifest
from pydantree.codegen.normalize import NormalizeOutput, normalize_ingested
from pydantree.runtime import WorkshopEventLogger, build_log_context, hash_for_path


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not getattr(args, "command", None):
        parser.print_help(sys.stderr)
        raise SystemExit(2)

    logger = WorkshopEventLogger()
    run_id = str(uuid4())

    try:
        _dispatch(args, logger=logger, run_id=run_id)
    except CodegenDiagnosticError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pydantree-codegen", description="Pydantree code generation pipeline")
    subparsers = parser.add_subparsers(dest="command")

    ingest = subparsers.add_parser("ingest", help="Discover .scm files and collect provenance")
    ingest.add_argument("root_dir", type=Path)
    ingest.add_argument("--out", type=Path, default=Path("build/ingest.json"))
    ingest.add_argument("--pattern", default="*.scm")

    normalize = subparsers.add_parser("normalize", help="Normalize ingested data into stable pattern IDs")
    normalize.add_argument("--input", type=Path, default=Path("build/ingest.json"), dest="input_path")
    normalize.add_argument("--out", type=Path, default=Path("build/normalize.json"))

    emit = subparsers.add_parser("emit", help="Generate deterministic Pydantic model modules")
    emit.add_argument("--input", type=Path, default=Path("build/normalize.json"), dest="input_path")
    emit.add_argument("--output-dir", type=Path, default=Path("build/generated"))
    emit.add_argument("--out", type=Path, default=Path("build/emit.json"))

    manifest = subparsers.add_parser("manifest", help="Build reproducibility metadata from stage artifacts")
    manifest.add_argument("--ingest", type=Path, default=Path("build/ingest.json"), dest="ingest_path")
    manifest.add_argument("--normalize", type=Path, default=Path("build/normalize.json"), dest="normalize_path")
    manifest.add_argument("--emit", type=Path, default=Path("build/emit.json"), dest="emit_path")
    manifest.add_argument("--out", type=Path, default=Path("build/manifest.json"))

    return parser


def _dispatch(args: argparse.Namespace, *, logger: WorkshopEventLogger, run_id: str) -> None:
    if args.command == "ingest":
        context = build_log_context(
            run_id=run_id,
            language="unknown",
            query_pack="unknown",
            source_hash=hash_for_path(args.root_dir),
        )
        logger.ingest_started(context)
        payload = ingest_scm(root_dir=args.root_dir, pattern=args.pattern)
        write_model(args.out, payload)
        logger.ingest_completed(context, files_discovered=len(payload.queries))
        print(f"Wrote ingest artifact: {args.out}")
        return

    if args.command == "normalize":
        ingest = IngestOutput.model_validate(read_model(args.input_path, IngestOutput))
        language = ingest.queries[0].provenance.language
        query_pack = Path(ingest.queries[0].provenance.file_path).stem
        context = build_log_context(
            run_id=run_id,
            language=language,
            query_pack=query_pack,
            source_hash=hash_for_path(args.input_path),
        )
        normalized = normalize_ingested(ingest)
        write_model(args.out, normalized)
        logger.normalize_completed(context, records_normalized=len(normalized.queries))
        print(f"Wrote normalize artifact: {args.out}")
        return

    if args.command == "emit":
        normalize = NormalizeOutput.model_validate(read_model(args.input_path, NormalizeOutput))
        language = normalize.queries[0].provenance.language
        query_pack = normalize.queries[0].provenance.query_type
        context = build_log_context(
            run_id=run_id,
            language=language,
            query_pack=query_pack,
            source_hash=hash_for_path(args.input_path),
        )
        try:
            emitted = emit_models(normalize, output_dir=args.output_dir)
        except CodegenDiagnosticError as exc:
            logger.generation_failed(context, error=str(exc))
            raise
        write_model(args.out, emitted)
        logger.generation_completed(context, models_generated=len(emitted.modules))
        print(f"Wrote emit artifact: {args.out}")
        return

    if args.command == "manifest":
        ingest = IngestOutput.model_validate(read_model(args.ingest_path, IngestOutput))
        normalize = NormalizeOutput.model_validate(read_model(args.normalize_path, NormalizeOutput))
        emit = EmitOutput.model_validate(read_model(args.emit_path, EmitOutput))
        manifest = build_manifest(ingest=ingest, normalize=normalize, emit=emit)
        write_model(args.out, manifest)
        print(f"Wrote manifest artifact: {args.out}")
        return

    raise CodegenDiagnosticError("cli", f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
