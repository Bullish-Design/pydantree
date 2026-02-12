from __future__ import annotations

import json
from pathlib import Path

import typer

from pydantree.doctor import format_human_summary, run_doctor

app = typer.Typer(help="Pydantree command line tools.")


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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
