#!/usr/bin/env python3
"""
/// script
/// requires-python = ">=3.9"
/// dependencies = [
///     "pydantic>=2.7.0",
///     "typer>=0.12.0",
///     "rich>=13.0.0",
///     "confidantic>=0.3.0",
/// ]
/// ///
"""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.console import Console
from pathlib import Path

from .api import PydantreeAPI
from .core.builders import PyClassBuilder, PyFunctionBuilder

app = typer.Typer(
    name="pydantree",
    help="A Pydantic-powered abstraction layer over GraphSitter"
)
console = Console()


@app.command()
def analyze(
    path: Path = typer.Argument(..., help="Path to analyze"),
    output: Path = typer.Option(
        None, "--output", "-o", help="Output file for analysis"
    )
) -> None:
    """Analyze existing codebase."""
    api = PydantreeAPI()
    rprint(f"[green]Analyzing:[/] {path}")
    # Placeholder for actual analysis
    rprint("[yellow]Analysis functionality pending GraphSitter integration[/]")


@app.command()
def create(
    name: str = typer.Argument(..., help="Component name"),
    component_type: str = typer.Option(
        "class", "--type", "-t", help="Component type (class/function)"
    )
) -> None:
    """Create new component."""
    if component_type == "class":
        builder = PyClassBuilder(name)
        cls = builder.build()
        rprint(f"[green]Created class:[/] {cls.class_name}")
        rprint(cls.to_class_definition())
    elif component_type == "function":
        builder = PyFunctionBuilder(name)
        func = builder.build()
        rprint(f"[green]Created function:[/] {func.function_name}")
        rprint(func.to_signature())
    else:
        rprint(f"[red]Error:[/] Unsupported type: {component_type}")


@app.command()
def validate(
    path: Path = typer.Argument(..., help="Path to validate")
) -> None:
    """Validate code structure."""
    api = PydantreeAPI()
    rprint(f"[green]Validating:[/] {path}")
    # Placeholder for actual validation
    rprint("[yellow]Validation functionality pending GraphSitter integration[/]")


if __name__ == "__main__":
    app()
