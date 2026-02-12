from __future__ import annotations

import argparse
import json
import sys
from uuid import uuid4
from pathlib import Path

from pydantree.codegen.common import CodegenDiagnosticError, read_model, write_model
from pydantree.codegen.emit import EmitOutput, emit_models
from pydantree.codegen.ingest import IngestOutput, ingest_scm
from pydantree.codegen.manifest import build_manifest
from pydantree.codegen.normalize import NormalizeOutput, NormalizedQuery, normalize_ingested
from pydantree.cue_validation import CueUnavailableError, ValidationResult, run_cue_validation
from pydantree.registry import WorkshopLayout, resolve_repository_root
from pydantree.runtime import WorkshopEventLogger, build_log_context, hash_for_path


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not getattr(args, "command", None):
        parser.print_help(sys.stderr)
        raise SystemExit(2)

    try:
        _dispatch(args, logger=WorkshopEventLogger(), run_id=str(uuid4()))
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

    generate = subparsers.add_parser(
        "generate",
        help="Run ingest/normalize/emit/manifest with CUE validation before and after generation",
    )
    generate.add_argument("root_dir", type=Path)
    generate.add_argument("--pattern", default="*.scm")
    generate.add_argument("--output-dir", type=Path, default=Path("build/generated"))
    generate.add_argument("--build-dir", type=Path, default=Path("build"))
    generate.add_argument("--schema-dir", type=Path, default=Path("src/pydantree/cue"))

    return parser


def _layout() -> WorkshopLayout:
    return WorkshopLayout.from_path(resolve_repository_root())


def _stage_file(layout: WorkshopLayout, *, language: str, query_pack: str, stage: str) -> Path:
    return layout.repository_root / "build" / language / query_pack / f"{stage}.json"


def _dispatch(args: argparse.Namespace, *, logger: WorkshopEventLogger, run_id: str) -> None:
    layout = _layout()

    if args.command == "ingest":
        root_dir = layout.queries_pack_dir(language=args.language, query_pack=args.query_pack)
        out = args.out or _stage_file(layout, language=args.language, query_pack=args.query_pack, stage="ingest")
        context = build_log_context(
            run_id=run_id,
            language=args.language,
            query_pack=args.query_pack,
            source_hash=hash_for_path(root_dir),
        )
        logger.ingest_started(context)
        payload = ingest_scm(root_dir=root_dir, pattern=args.pattern)
        write_model(out, payload)
        logger.ingest_completed(context, files_discovered=len(payload.queries))
        print(f"Wrote ingest artifact: {out}")
        return

    if args.command == "normalize":
        input_path = args.input_path or _stage_file(
            layout,
            language=args.language,
            query_pack=args.query_pack,
            stage="ingest",
        )
        out = args.out or layout.ir_file(language=args.language, query_pack=args.query_pack)
        ingest = IngestOutput.model_validate(read_model(input_path, IngestOutput))
        context = build_log_context(
            run_id=run_id,
            language=args.language,
            query_pack=args.query_pack,
            source_hash=hash_for_path(input_path),
        )
        normalized = normalize_ingested(ingest)
        write_model(out, normalized)
        logger.normalize_completed(context, records_normalized=len(normalized.queries))
        print(f"Wrote normalize artifact: {out}")
        return

    if args.command == "emit":
        input_path = args.input_path or layout.ir_file(language=args.language, query_pack=args.query_pack)
        output_dir = args.output_dir or layout.generated_models_dir(language=args.language, query_pack=args.query_pack)
        out = args.out or _stage_file(layout, language=args.language, query_pack=args.query_pack, stage="emit")
        normalize = NormalizeOutput.model_validate(read_model(input_path, NormalizeOutput))
        context = build_log_context(
            run_id=run_id,
            language=args.language,
            query_pack=args.query_pack,
            source_hash=hash_for_path(input_path),
        )
        try:
            emitted = emit_models(normalize, output_dir=output_dir)
        except CodegenDiagnosticError as exc:
            logger.generation_failed(context, error=str(exc))
            raise
        write_model(out, emitted)
        logger.generation_completed(context, models_generated=len(emitted.modules))
        print(f"Wrote emit artifact: {out}")
        return

    if args.command == "manifest":
        ingest_path = args.ingest_path or _stage_file(
            layout,
            language=args.language,
            query_pack=args.query_pack,
            stage="ingest",
        )
        normalize_path = args.normalize_path or layout.ir_file(language=args.language, query_pack=args.query_pack)
        emit_path = args.emit_path or _stage_file(layout, language=args.language, query_pack=args.query_pack, stage="emit")
        out = args.out or layout.manifest_file(language=args.language, query_pack=args.query_pack)
        ingest = IngestOutput.model_validate(read_model(ingest_path, IngestOutput))
        normalize = NormalizeOutput.model_validate(read_model(normalize_path, NormalizeOutput))
        emit = EmitOutput.model_validate(read_model(emit_path, EmitOutput))
        manifest = build_manifest(ingest=ingest, normalize=normalize, emit=emit)
        write_model(out, manifest)
        print(f"Wrote manifest artifact: {out}")
        return

    if args.command == "generate":
        ingest = ingest_scm(root_dir=args.root_dir, pattern=args.pattern)
        normalize = normalize_ingested(ingest)

        build_dir: Path = args.build_dir
        build_dir.mkdir(parents=True, exist_ok=True)
        ir_schema = _schema_path(args.schema_dir, "ir_schema.cue")

        for query in normalize.queries:
            ir_file = build_dir / f"ir.{query.provenance.language}.{query.provenance.query_type}.json"
            ir_file.write_text(json.dumps(_query_ir_payload(query), indent=2), encoding="utf-8")
            try:
                validation = run_cue_validation(ir_file, ir_schema)
            except CueUnavailableError as exc:
                raise CodegenDiagnosticError("generate", str(exc)) from exc
            _emit_validation(f"Pre-generation IR validation ({query.provenance.file_path})", validation)
            if not validation.ok:
                raise CodegenDiagnosticError("generate", f"IR validation failed for {query.provenance.file_path}")

        emitted = emit_models(normalize, output_dir=args.output_dir)
        manifest = build_manifest(ingest=ingest, normalize=normalize, emit=emitted)

        ingest_out = build_dir / "ingest.json"
        normalize_out = build_dir / "normalize.json"
        emit_out = build_dir / "emit.json"
        manifest_out = build_dir / "manifest.json"
        write_model(ingest_out, ingest)
        write_model(normalize_out, normalize)
        write_model(emit_out, emitted)
        write_model(manifest_out, manifest)

        manifest_schema = _schema_path(args.schema_dir, "manifest_schema.cue")
        try:
            validation = run_cue_validation(manifest_out, manifest_schema)
        except CueUnavailableError as exc:
            raise CodegenDiagnosticError("generate", str(exc)) from exc
        _emit_validation("Post-generation manifest validation", validation)
        if not validation.ok:
            raise CodegenDiagnosticError("generate", "Manifest validation failed")

        print(f"Wrote ingest artifact: {ingest_out}")
        print(f"Wrote normalize artifact: {normalize_out}")
        print(f"Wrote emit artifact: {emit_out}")
        print(f"Wrote manifest artifact: {manifest_out}")
        return

    raise CodegenDiagnosticError("codegen", f"Unsupported command: {args.command}")


def _schema_path(schema_dir: Path, name: str) -> Path:
    return schema_dir / name


def _emit_validation(result_name: str, result: ValidationResult) -> None:
    if result.ok:
        print(f"{result_name}: ok")
        return
    print(f"{result_name}: failed", file=sys.stderr)
    for detail in result.details:
        print(f"  - {detail}", file=sys.stderr)


def _query_ir_payload(query: object) -> dict[str, object]:
    from pydantree.codegen.normalize import NormalizedQuery

    normalized = NormalizedQuery.model_validate(query)
    return {
        "version": "v1",
        "patterns": [
            {
                "id": pattern.pattern_id,
                "pattern": pattern.source,
                "captures": [
                    {
                        "name": capture.name,
                        "source": {"file": normalized.provenance.file_path},
                    }
                    for capture in pattern.captures
                ],
            }
            for pattern in normalized.patterns
        ],
        "query_metadata": {
            "language": normalized.provenance.language,
            "query_type": normalized.provenance.query_type,
            "source_scm": normalized.provenance.file_path,
            "generated_by": "pydantree-codegen",
        },
    }


def _layout() -> WorkshopLayout:
    return WorkshopLayout.from_path(resolve_repository_root())


def _schema_path(schema_dir: Path, name: str) -> Path:
    return schema_dir / name


def _emit_validation(result_name: str, result: ValidationResult) -> None:
    if result.ok:
        print(f"{result_name}: ok")
        return
    print(f"{result_name}: failed", file=sys.stderr)
    for detail in result.details:
        print(f"  - {detail}", file=sys.stderr)


def _query_ir_payload(query: object) -> dict[str, object]:
    normalized = NormalizedQuery.model_validate(query)
    return {
        "version": "v1",
        "patterns": [
            {
                "id": pattern.pattern_id,
                "pattern": pattern.source,
                "captures": [
                    {
                        "name": capture.name,
                        "source": {"file": normalized.provenance.file_path},
                    }
                    for capture in pattern.captures
                ],
            }
            for pattern in normalized.patterns
        ],
        "query_metadata": {
            "language": normalized.provenance.language,
            "query_type": normalized.provenance.query_type,
            "source_scm": normalized.provenance.file_path,
            "generated_by": "pydantree-codegen",
        },
    }


if __name__ == "__main__":
    main()
