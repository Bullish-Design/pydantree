from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

import typer

from pydantree.doctor import format_human_summary, run_doctor
from pydantree.cue_validation import CueUnavailableError, run_cue_validation

app = typer.Typer(help="Pydantree generation wrappers with CUE validation gates.")


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
    try:
        result = run_cue_validation(ir_file, schema_file)
    except CueUnavailableError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc

    _emit_validation_result("IR validation", result.ok, result.details)
    if not result.ok:
        raise typer.Exit(code=1)


@app.command("validate-manifest")
def validate_manifest(
    manifest_file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    schema_dir: Path | None = typer.Option(None, help="Optional directory containing CUE schemas."),
) -> None:
    schema_file = _schema_path("manifest_schema.cue", schema_dir)
    try:
        result = run_cue_validation(manifest_file, schema_file)
    except CueUnavailableError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc

    _emit_validation_result("Manifest validation", result.ok, result.details)
    if not result.ok:
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

    try:
        pre_result = run_cue_validation(ir_file, ir_schema)
    except CueUnavailableError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc

    _emit_validation_result("Pre-generation IR validation", pre_result.ok, pre_result.details)
    if not pre_result.ok:
        raise typer.Exit(code=1)

    command_parts = shlex.split(generator_cmd)
    generation = subprocess.run(command_parts, check=False, text=True, capture_output=True)
    if generation.stdout:
        typer.echo(generation.stdout.rstrip())
    if generation.returncode != 0:
        if generation.stderr:
            typer.echo(generation.stderr.rstrip())
        raise typer.Exit(code=generation.returncode)

    post_result = run_cue_validation(manifest_file, manifest_schema)
    _emit_validation_result("Post-generation manifest validation", post_result.ok, post_result.details)
    if not post_result.ok:
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    app()
