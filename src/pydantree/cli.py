#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic>=2.11",
#     "tree-sitter>=0.23",
#     "tree-sitter-python>=0.23.6",
#     "typer>=0.12.0",
#     "rich>=13.0.0",
# ]
# ///


"""
pydantree.cli – Command-line interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Typer-based CLI with rich output for code generation, AST analysis,
querying, transformation, and graph operations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree
from rich.json import JSON

"""
try:
    import typer
    from rich.console import Console
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.tree import Tree
    from rich.json import JSON

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

    # Fallback basic implementation
    class typer:
        @staticmethod
        def run(func):
            return func

        Typer = dict

    Console = lambda: None
"""


from .codegen import generate_from_node_types
from .core import TSNode
from .parser import Parser
from .incremental import ParsedDocument
from .views import parse_python
from .nodegroup import NodeGroup

app = typer.Typer(
    name="pydantree",
    help="Typed Tree-sitter wrapper with graph operations",
    rich_markup_mode="rich",  # if HAS_RICH else None,
)

console = Console()  # if HAS_RICH else None


def _load_python_language():
    """Load Python language for parsing."""
    try:
        import tree_sitter_python as tspy
        from tree_sitter import Language

        return Language(tspy.language())
    except ImportError:
        typer.echo("Error: tree-sitter-python not installed", err=True)
        raise typer.Exit(1)


@app.command()
def generate(
    node_types_json: Path = typer.Argument(..., help="Path to node-types.json file"),
    output: Path = typer.Option(..., "--out", "-o", help="Output Python file path"),
    token_suffix: str = typer.Option(
        "TokenNode", "--token-suffix", help="Suffix for anonymous tokens"
    ),
    base_class: str = typer.Option(
        "TSNode", "--base-class", help="Base class for generated nodes"
    ),
) -> None:
    """Generate typed node classes from node-types.json."""
    try:
        generate_from_node_types(node_types_json, output, token_suffix, base_class)
        if console:
            console.print(f"✅ Generated [bold]{output}[/bold]")
        else:
            print(f"Generated {output}")
    except Exception as e:
        if console:
            console.print(f"❌ Error: {e}", style="red")
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(1)


@app.command()
def ast(
    source: Optional[Path] = typer.Argument(None, help="Python source file"),
    code: Optional[str] = typer.Option(None, "--code", "-c", help="Inline code"),
    max_depth: int = typer.Option(4, "--depth", help="Maximum tree depth"),
    show_text: bool = typer.Option(True, "--text/--no-text", help="Show node text"),
    format: str = typer.Option("tree", "--format", help="Output format: tree, json"),
) -> None:
    """Display AST for Python code."""
    if not source and not code:
        if console:
            console.print("❌ Provide either source file or --code", style="red")
        else:
            print("Error: Provide either source file or --code", file=sys.stderr)
        raise typer.Exit(1)

    if source:
        code = source.read_text()

    try:
        lang = _load_python_language()
        parser = Parser(lang)
        doc = ParsedDocument(text=code, parser=parser)

        if format == "json":
            if console:
                console.print(JSON(doc.root.model_dump_json()))
            else:
                print(json.dumps(doc.root.dict(), indent=2))
        else:
            if console:
                _print_tree_rich(doc.root, max_depth, show_text)
            else:
                print(doc.root.pretty())

    except Exception as e:
        if console:
            console.print(f"❌ Error: {e}", style="red")
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(1)


def _print_tree_rich(node: TSNode, max_depth: int, show_text: bool, depth: int = 0):
    """Print AST as rich tree."""
    if not console:
        return

    tree = Tree(f"[bold]{node.__class__.__name__}[/bold]")
    _add_tree_children(tree, node, max_depth, show_text, depth)
    console.print(tree)


def _add_tree_children(tree, node: TSNode, max_depth: int, show_text: bool, depth: int):
    """Recursively add children to rich tree."""
    if depth >= max_depth:
        return

    for child in node.children:
        if not child.is_named:
            continue
        label = f"[bold]{child.__class__.__name__}[/bold]"
        if show_text and child.text.strip():
            text = child.text.strip().replace("\n", " ")[:40]
            if len(text) == 40:
                text += "..."
            label += f": [dim]{text}[/dim]"

        child_tree = tree.add(label)
        _add_tree_children(child_tree, child, max_depth, show_text, depth + 1)


@app.command()
def query(
    source: Optional[Path] = typer.Argument(None, help="Python source file"),
    code: Optional[str] = typer.Option(None, "--code", "-c", help="Inline code"),
    node_type: Optional[str] = typer.Option(None, "--type", help="Filter by node type"),
    class_name: Optional[str] = typer.Option(
        None, "--class", help="Filter by class name"
    ),
    text_contains: Optional[str] = typer.Option(None, "--text", help="Text contains"),
    count_only: bool = typer.Option(False, "--count", help="Show count only"),
) -> None:
    """Query AST nodes with filters."""
    if not source and not code:
        if console:
            console.print("❌ Provide either source file or --code", style="red")
        else:
            print("Error: Provide either source file or --code", file=sys.stderr)
        raise typer.Exit(1)

    if source:
        code = source.read_text()

    try:
        module = parse_python(code)
        nodegroup = NodeGroup.from_tree(module.node)

        # Apply filters
        if node_type:
            nodegroup = nodegroup.filter_type(node_type)
        if text_contains:
            nodegroup = nodegroup.filter_text(text_contains, exact=False)

        results = list(nodegroup)

        if count_only:
            if console:
                console.print(f"Count: [bold]{len(results)}[/bold]")
            else:
                print(f"Count: {len(results)}")
        else:
            if console:
                table = Table(title="Query Results")
                table.add_column("Type", style="cyan")
                table.add_column("Text", style="green")
                table.add_column("Position", style="dim")

                for node in results[:20]:  # Limit output
                    text = node.text.strip().replace("\n", " ")[:50]
                    pos = f"{node.start_point.row}:{node.start_point.column}"
                    table.add_row(node.type_name, text, pos)

                console.print(table)
            else:
                for node in results[:20]:
                    print(f"{node.type_name}: {node.text.strip()[:50]}")

    except Exception as e:
        if console:
            console.print(f"❌ Error: {e}", style="red")
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(1)


@app.command()
def transform(
    source: Path = typer.Argument(..., help="Python source file"),
    output: Optional[Path] = typer.Option(None, "--out", "-o", help="Output file"),
    transformer: str = typer.Option(
        "print_to_logger", "--transform", help="Transformer name"
    ),
) -> None:
    """Apply code transformations."""
    try:
        from .views import PyTransformer

        code = source.read_text()
        module = parse_python(code)

        # Built-in transformers
        if transformer == "print_to_logger":

            class PrintToLogger(PyTransformer):
                def visit_expression_statement(self, node):
                    text = node.text.lstrip()
                    if text.startswith("print("):
                        return node.text.replace("print(", "logger.info(", 1)

            transformed = PrintToLogger(module).visit()
        else:
            if console:
                console.print(f"❌ Unknown transformer: {transformer}", style="red")
            else:
                print(f"Error: Unknown transformer: {transformer}", file=sys.stderr)
            raise typer.Exit(1)

        if output:
            output.write_text(transformed)
            if console:
                console.print(f"✅ Transformed code written to [bold]{output}[/bold]")
            else:
                print(f"Transformed code written to {output}")
        else:
            if console:
                console.print(Syntax(transformed, "python"))
            else:
                print(transformed)

    except Exception as e:
        if console:
            console.print(f"❌ Error: {e}", style="red")
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(1)


@app.command()
def graph(
    source: Optional[Path] = typer.Argument(None, help="Python source file"),
    code: Optional[str] = typer.Option(None, "--code", "-c", help="Inline code"),
    include_siblings: bool = typer.Option(
        False, "--siblings", help="Include sibling edges"
    ),
    format: str = typer.Option("stats", "--format", help="Output format: stats, dot"),
) -> None:
    """Convert AST to graph and show analysis."""
    try:
        from .graph import GraphBuilder, GraphAnalyzer
    except ImportError:
        if console:
            console.print("❌ Graph operations require rustworkx", style="red")
        else:
            print("Error: Graph operations require rustworkx", file=sys.stderr)
        raise typer.Exit(1)

    if not source and not code:
        if console:
            console.print("❌ Provide either source file or --code", style="red")
        else:
            print("Error: Provide either source file or --code", file=sys.stderr)
        raise typer.Exit(1)

    if source:
        code = source.read_text()

    try:
        module = parse_python(code)
        nodegroup = NodeGroup.from_tree(module.node)

        builder = GraphBuilder(nodegroup)
        graph = builder.to_graph(include_siblings=include_siblings)
        analyzer = GraphAnalyzer(graph)

        if format == "stats":
            metrics = analyzer.graph_metrics()
            if console:
                table = Table(title="Graph Statistics")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")

                for key, value in metrics.items():
                    table.add_row(key.replace("_", " ").title(), str(value))

                console.print(table)
            else:
                for key, value in metrics.items():
                    print(f"{key}: {value}")
        else:
            if console:
                console.print("❌ DOT format not yet implemented", style="red")
            else:
                print("Error: DOT format not yet implemented", file=sys.stderr)

    except Exception as e:
        if console:
            console.print(f"❌ Error: {e}", style="red")
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(1)


def main() -> None:
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
