from __future__ import annotations

import json
import shlex
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import typer

from pydantree.codegen.common import CodegenDiagnosticError, read_model, write_model
from pydantree.codegen.emit import EmitOutput, emit_models
from pydantree.codegen.ingest import IngestOutput, ingest_scm
from pydantree.codegen.manifest import build_manifest
from pydantree.codegen.normalize import NormalizeOutput, normalize_ingested
from pydantree.doctor import format_human_summary, run_doctor
from pydantree.cue_validation import CueUnavailableError, run_cue_validation
from pydantree.models import LogContext
from pydantree.runtime import WorkshopEventLogger, build_log_context, hash_for_path

app = typer.Typer(help="Pydantree generation wrappers with CUE validation gates.")




def _context_for_path(path: Path, *, run_id: str) -> LogContext:
    return build_log_context(
        run_id=run_id,
        language="unknown",
        query_pack=path.stem,
        source_hash=hash_for_path(path),
    )
@app.command("codegen-ingest")
def codegen_ingest(
    root_dir: Path = typer.Argument(..., exists=True, file_okay=False, readable=True),
    out: Path = typer.Option(Path("build/ingest.json"), help="Output JSON artifact path."),
    pattern: str = typer.Option("*.scm", help="Glob used for query discovery."),
) -> None:
    """Discover .scm files and collect provenance metadata."""
    try:
        payload = ingest_scm(root_dir=root_dir, pattern=pattern)
    except CodegenDiagnosticError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc
    write_model(out, payload)
    typer.echo(f"Wrote ingest artifact: {out}")


@app.command("codegen-normalize")
def codegen_normalize(
    input_path: Path = typer.Option(Path("build/ingest.json"), "--input", help="Ingest artifact path."),
    out: Path = typer.Option(Path("build/normalize.json"), help="Output JSON artifact path."),
) -> None:
    """Normalize ingested queries into stable pattern IDs."""
    try:
        ingest = IngestOutput.model_validate(read_model(input_path, IngestOutput))
        normalized = normalize_ingested(ingest)
    except CodegenDiagnosticError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc
    write_model(out, normalized)
    typer.echo(f"Wrote normalize artifact: {out}")


@app.command("codegen-emit")
def codegen_emit(
    input_path: Path = typer.Option(Path("build/normalize.json"), "--input", help="Normalize artifact path."),
    output_dir: Path = typer.Option(Path("build/generated"), help="Directory for generated modules."),
    out: Path = typer.Option(Path("build/emit.json"), help="Output JSON artifact path."),
) -> None:
    """Generate deterministic Pydantic modules from normalized queries."""
    try:
        normalize = NormalizeOutput.model_validate(read_model(input_path, NormalizeOutput))
        emitted = emit_models(normalize, output_dir=output_dir)
    except CodegenDiagnosticError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc
    write_model(out, emitted)
    typer.echo(f"Wrote emit artifact: {out}")


@app.command("codegen-manifest")
def codegen_manifest(
    ingest_path: Path = typer.Option(Path("build/ingest.json"), "--ingest", help="Ingest artifact path."),
    normalize_path: Path = typer.Option(Path("build/normalize.json"), "--normalize", help="Normalize artifact path."),
    emit_path: Path = typer.Option(Path("build/emit.json"), "--emit", help="Emit artifact path."),
    out: Path = typer.Option(Path("build/manifest.json"), help="Output manifest artifact path."),
) -> None:
    """Build reproducibility metadata for the complete codegen pipeline."""
    try:
        ingest = IngestOutput.model_validate(read_model(ingest_path, IngestOutput))
        normalize = NormalizeOutput.model_validate(read_model(normalize_path, NormalizeOutput))
        emit = EmitOutput.model_validate(read_model(emit_path, EmitOutput))
        manifest = build_manifest(ingest=ingest, normalize=normalize, emit=emit)
    except CodegenDiagnosticError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc
    write_model(out, manifest)
    typer.echo(f"Wrote manifest artifact: {out}")


@app.command("doctor")
def doctor_command(
    queries_dir: Path = typer.Option(Path("queries"), help="Directory containing .scm query files."),
    manifest: Path = typer.Option(Path("generated/manifest.json"), help="Path to generation manifest JSON file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Run diagnostics over query sources, generation artifacts, and runtime dependencies."""
    repo_root = Path.cwd()
    result = run_doctor(
        repo_root=repo_root,
        queries_dir=(repo_root / queries_dir).resolve(),
        manifest_path=(repo_root / manifest).resolve(),
    )

    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
    else:
        typer.echo(format_human_summary(result))

    raise typer.Exit(0 if result["ok"] else 1)


def _schema_path(schema_name: str, schema_dir: Path | None = None) -> Path:
    if schema_dir is not None:
        return schema_dir / schema_name
    return Path(__file__).resolve().parent / "cue" / schema_name


def _emit_validation_result(result_name: str, ok: bool, details: list[str]) -> None:
    if ok:
        typer.echo(f"{result_name}: ok")
        return
    typer.echo(f"{result_name}: failed")
    for detail in details:
        typer.echo(f"  - {detail}")


@app.command("validate-ir")
def validate_ir(
    ir_file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    schema_dir: Path | None = typer.Option(None, help="Optional directory containing CUE schemas."),
) -> None:
    schema_file = _schema_path("ir_schema.cue", schema_dir)
    logger = WorkshopEventLogger()
    context = _context_for_path(ir_file, run_id=str(uuid4()))
    try:
        result = run_cue_validation(ir_file, schema_file)
    except CueUnavailableError as exc:
        typer.echo(str(exc))
        logger.validation_failed(context, error=str(exc))
        raise typer.Exit(code=2) from exc

    _emit_validation_result("IR validation", result.ok, result.details)
    if result.ok:
        logger.validation_completed(context, checks_run=1)
    else:
        logger.validation_failed(context, error="; ".join(result.details) or "validation failed")
        raise typer.Exit(code=1)


@app.command("validate-manifest")
def validate_manifest(
    manifest_file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    schema_dir: Path | None = typer.Option(None, help="Optional directory containing CUE schemas."),
) -> None:
    schema_file = _schema_path("manifest_schema.cue", schema_dir)
    logger = WorkshopEventLogger()
    context = _context_for_path(manifest_file, run_id=str(uuid4()))
    try:
        result = run_cue_validation(manifest_file, schema_file)
    except CueUnavailableError as exc:
        typer.echo(str(exc))
        logger.validation_failed(context, error=str(exc))
        raise typer.Exit(code=2) from exc

    _emit_validation_result("Manifest validation", result.ok, result.details)
    if result.ok:
        logger.validation_completed(context, checks_run=1)
    else:
        logger.validation_failed(context, error="; ".join(result.details) or "validation failed")
        raise typer.Exit(code=1)


@app.command("generate")
def generate(
    ir_file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    manifest_file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    generator_cmd: str = typer.Option(..., help="Shell command used for generation."),
    schema_dir: Path | None = typer.Option(None, help="Optional directory containing CUE schemas."),
) -> None:
    ir_schema = _schema_path("ir_schema.cue", schema_dir)
    manifest_schema = _schema_path("manifest_schema.cue", schema_dir)
    logger = WorkshopEventLogger()
    run_id = str(uuid4())
    context = _context_for_path(ir_file, run_id=run_id)

    try:
        pre_result = run_cue_validation(ir_file, ir_schema)
    except CueUnavailableError as exc:
        typer.echo(str(exc))
        logger.validation_failed(context, error=str(exc))
        raise typer.Exit(code=2) from exc

    _emit_validation_result("Pre-generation IR validation", pre_result.ok, pre_result.details)
    if pre_result.ok:
        logger.validation_completed(context, checks_run=1)
    else:
        logger.validation_failed(context, error="; ".join(pre_result.details) or "pre-generation validation failed")
        raise typer.Exit(code=1)

    command_parts = shlex.split(generator_cmd)
    started = time.perf_counter()
    generation = subprocess.run(command_parts, check=False, text=True, capture_output=True)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.query_runtime_execution(context, target=generator_cmd, elapsed_ms=elapsed_ms)

    if generation.stdout:
        typer.echo(generation.stdout.rstrip())
    if generation.returncode != 0:
        if generation.stderr:
            typer.echo(generation.stderr.rstrip())
        logger.generation_failed(context, error=f"exit code {generation.returncode}")
        raise typer.Exit(code=generation.returncode)

    logger.generation_completed(context, models_generated=1)

    post_result = run_cue_validation(manifest_file, manifest_schema)
    _emit_validation_result("Post-generation manifest validation", post_result.ok, post_result.details)
    if post_result.ok:
        logger.validation_completed(_context_for_path(manifest_file, run_id=run_id), checks_run=1)
    else:
        logger.validation_failed(
            _context_for_path(manifest_file, run_id=run_id),
            error="; ".join(post_result.details) or "post-generation validation failed",
        )
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    app()
