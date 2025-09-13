# pydantree/cli/main.py
from __future__ import annotations

import sys
import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn, MofNCompleteColumn
from rich.table import Table
from rich.tree import Tree as RichTree
from rich.panel import Panel
from rich.syntax import Syntax
from rich.json import JSON
from rich.text import Text
from rich.columns import Columns
from rich.align import Align

from ..core.parsers import Parser, MultiLanguageParser#, LanguageRegistry
from ..core.nodes import TSNode
from ..core.profiler import PerformanceProfiler
from ..processing.batch import BatchProcessor, ProcessingMode, ProcessingPriority, discover_source_files
from ..export.engine import ExportEngine, ExportOptions, ExportFormat, OutputFormat, CompressionType

from .commands import batch_app


app = typer.Typer(
    name="pydantree",
    help="[bold blue]Pydantree[/bold blue] - High-performance multi-language AST analysis platform",
    rich_markup_mode="rich",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]}
)

console = Console()


def version_callback(show_version: bool):
    """Show version information."""
    if show_version:
        try:
            from .._version import __version__
        except ImportError:
            __version__ = "development"
        
        console.print(f"[bold blue]Pydantree[/bold blue] version [green]{__version__}[/green]")
        console.print("High-performance multi-language AST analysis platform")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", callback=version_callback, 
                                help="Show version information"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-essential output")
):
    """Pydantree CLI - Multi-language AST analysis and processing."""
    if verbose:
        console.print("[dim]Verbose mode enabled[/dim]")
    elif quiet:
        console.quiet = True

#@app.command()
#batch_app

# ========================================================================
# Code Generation Commands
# ========================================================================

@app.command()
def generate(
    node_types_json: Path = typer.Argument(..., help="Path to node-types.json file"),
    output: Path = typer.Option(..., "--out", "-o", help="Output Python file path"),
    language: str = typer.Option("generic", "--language", "-l", help="Target language name"),
    token_suffix: str = typer.Option("TokenNode", "--token-suffix", help="Suffix for anonymous tokens"),
    base_class: str = typer.Option("TSNode", "--base-class", help="Base class for generated nodes"),
    include_metadata: bool = typer.Option(True, "--metadata/--no-metadata", help="Include field metadata"),
    format_code: bool = typer.Option(True, "--format/--no-format", help="Format generated code")
):
    """Generate typed node classes from node-types.json with language-specific optimizations."""
    try:
        from ..codegen.generator import generate_from_node_types
        
        with console.status(f"[spinner]Generating classes for {language}..."):
            generate_from_node_types(
                node_types_json,
                output,
                language=language,
                token_suffix=token_suffix,
                base_class=base_class,
                include_metadata=include_metadata,
                format_code=format_code
            )
        
        # Show statistics
        generated_lines = output.read_text().count('\n')
        file_size = output.stat().st_size / 1024  # KB
        
        stats_table = Table(title="Generation Summary", show_header=False)
        stats_table.add_row("Language", f"[green]{language}[/green]")
        stats_table.add_row("Output File", f"[blue]{output}[/blue]")
        stats_table.add_row("Lines Generated", f"{generated_lines:,}")
        stats_table.add_row("File Size", f"{file_size:.1f} KB")
        
        console.print(stats_table)
        console.print(f"✅ [green]Generation complete[/green]")
        
    except Exception as e:
        console.print(f"❌ [red]Error:[/red] {e}")
        raise typer.Exit(1)


# ========================================================================
# Analysis Commands  
# ========================================================================

@app.command()
def analyze(
    source: Path = typer.Argument(..., help="Source file or directory to analyze"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Language (auto-detect if not specified)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file for results"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv"),
    metrics: str = typer.Option("all", "--metrics", "-m", help="Metrics: all, basic, advanced, complexity"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r", help="Search recursively"),
    include_errors: bool = typer.Option(False, "--include-errors", help="Include files with parse errors"),
    max_files: Optional[int] = typer.Option(None, "--max-files", help="Maximum files to process"),
    workers: int = typer.Option(4, "--workers", "-w", help="Number of parallel workers"),
    show_progress: bool = typer.Option(True, "--progress/--no-progress", help="Show progress bars")
):
    """Analyze code files with comprehensive metrics and multi-language support."""
    
    if not source.exists():
        console.print(f"❌ [red]Source not found:[/red] {source}")
        raise typer.Exit(1)
    
    profiler = PerformanceProfiler(enabled=True)
    
    with profiler.profile('analysis_command'):
        # Initialize parser
        if source.is_file():
            if language:
                parser = Parser.for_language(language, profiler=profiler)
            else:
                parser = Parser.auto_detect(source, profiler=profiler)
            
            # Analyze single file
            results = [_analyze_single_file(source, parser, metrics, profiler)]
        else:
            # Directory analysis
            results = _analyze_directory(
                source, language, metrics, recursive, workers, 
                max_files, show_progress, profiler
            )
    
    # Display results
    if not results:
        console.print("⚠️  [yellow]No files analyzed[/yellow]")
        return
    
    # Filter out errors if not requested
    if not include_errors:
        results = [r for r in results if r['success']]
    
    # Output results
    if output:
        _export_analysis_results(results, output, format)
        console.print(f"📄 Results exported to [blue]{output}[/blue]")
    else:
        _display_analysis_results(results, format)
    
    # Show performance summary
    perf_stats = profiler.get_detailed_report()
    console.print(f"\n⚡ Analysis completed in {perf_stats['summary']['total_time']}")


def _analyze_single_file(file_path: Path, parser: Parser, metrics: str, profiler: PerformanceProfiler) -> Dict[str, Any]:
    """Analyze a single file."""
    try:
        with profiler.profile(f'parse_{file_path.name}'):
            node = parser.parse_file(file_path)
        
        with profiler.profile(f'metrics_{file_path.name}'):
            include_advanced = metrics in ['all', 'advanced']
            file_metrics = node.get_metrics(include_advanced=include_advanced)
        
        return {
            'file': str(file_path),
            'language': parser.language_name,
            'success': True,
            'metrics': file_metrics,
            'size_kb': file_path.stat().st_size / 1024
        }
        
    except Exception as e:
        return {
            'file': str(file_path),
            'success': False,
            'error': str(e),
            'size_kb': 0
        }


def _analyze_directory(source: Path, language: Optional[str], metrics: str, 
                      recursive: bool, workers: int, max_files: Optional[int],
                      show_progress: bool, profiler: PerformanceProfiler) -> List[Dict[str, Any]]:
    """Analyze directory with batch processing."""
    
    # Discover files
    if language:
        files = discover_source_files(source, [language])
    else:
        # Auto-discover all supported files
        files = []
        for lang in LanguageRegistry.get_supported_languages():
            lang_files = discover_source_files(source, [lang])
            files.extend(lang_files)
        files = list(set(files))  # Deduplicate
    
    if max_files:
        files = files[:max_files]
    
    console.print(f"📁 Found {len(files):,} files to analyze")
    
    # Setup batch processor
    if language:
        parser = Parser.for_language(language, profiler=profiler)
    else:
        supported_languages = LanguageRegistry.get_supported_languages()
        parser = MultiLanguageParser(supported_languages, profiler=profiler)
    
    processor = BatchProcessor(
        parser=parser,
        batch_size=100,
        profiler=profiler,
        max_workers=workers,
        mode=ProcessingMode.THREADED
    )
    
    # Process files
    results = []
    include_advanced = metrics in ['all', 'advanced']
    
    if show_progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Processing files...", total=len(files))
            
            for batch_result in processor.process_files(files, include_metrics=include_advanced):
                for file_result in batch_result.files:
                    if file_result.success:
                        results.append({
                            'file': str(file_result.path),
                            'language': file_result.language,
                            'success': True,
                            'metrics': file_result.metrics,
                            'size_kb': file_result.file_size / 1024,
                            'parse_time': file_result.parse_time
                        })
                    else:
                        results.append({
                            'file': str(file_result.path),
                            'success': False,
                            'error': file_result.error,
                            'parse_time': file_result.parse_time
                        })
                
                progress.advance(task, len(batch_result.files))
    else:
        # Process without progress bar
        for batch_result in processor.process_files(files, include_metrics=include_advanced):
            for file_result in batch_result.files:
                if file_result.success:
                    results.append({
                        'file': str(file_result.path),
                        'language': file_result.language,
                        'success': True,
                        'metrics': file_result.metrics,
                        'size_kb': file_result.file_size / 1024,
                        'parse_time': file_result.parse_time
                    })
                else:
                    results.append({
                        'file': str(file_result.path),
                        'success': False,
                        'error': file_result.error,
                        'parse_time': file_result.parse_time
                    })
    
    return results


def _display_analysis_results(results: List[Dict[str, Any]], format: str):
    """Display analysis results in specified format."""
    
    if format == "json":
        console.print(JSON(json.dumps(results, indent=2)))
    elif format == "csv":
        # Simple CSV display
        if results:
            headers = ['File', 'Language', 'Functions', 'Classes', 'Complexity', 'Size (KB)']
            console.print(','.join(headers))
            
            for result in results:
                if result['success']:
                    metrics = result['metrics']
                    row = [
                        Path(result['file']).name,
                        result['language'],
                        str(metrics.get('functions', 0)),
                        str(metrics.get('classes', 0)),
                        str(metrics.get('cyclomatic_complexity', 0)),
                        f"{result['size_kb']:.1f}"
                    ]
                    console.print(','.join(row))
    else:  # table format
        _display_analysis_table(results)


def _display_analysis_table(results: List[Dict[str, Any]]):
    """Display analysis results as formatted table."""
    
    if not results:
        return
    
    successful_results = [r for r in results if r['success']]
    
    # Summary statistics
    total_files = len(results)
    successful_files = len(successful_results)
    
    if successful_files > 0:
        # Aggregate statistics
        total_functions = sum(r['metrics'].get('functions', 0) for r in successful_results)
        total_classes = sum(r['metrics'].get('classes', 0) for r in successful_results)
        avg_complexity = sum(r['metrics'].get('cyclomatic_complexity', 0) for r in successful_results) / successful_files
        total_size = sum(r['size_kb'] for r in successful_results)
        
        # Summary panel
        summary_text = f"""[green]{successful_files}[/green] files analyzed successfully
[yellow]{total_files - successful_files}[/yellow] files failed
[blue]{total_functions:,}[/blue] functions found
[blue]{total_classes:,}[/blue] classes found
[magenta]{avg_complexity:.1f}[/magenta] average complexity
[cyan]{total_size:.1f} KB[/cyan] total size"""
        
        console.print(Panel(summary_text, title="Analysis Summary"))
        
        # Detailed table for top files
        table = Table(title="File Analysis Results", show_lines=True)
        table.add_column("File", style="cyan", max_width=40)
        table.add_column("Language", style="blue")
        table.add_column("Functions", justify="right", style="green")
        table.add_column("Classes", justify="right", style="yellow")
        table.add_column("Complexity", justify="right", style="red")
        table.add_column("Size (KB)", justify="right", style="dim")
        
        # Show top 20 files by complexity
        sorted_results = sorted(successful_results, 
                              key=lambda x: x['metrics'].get('cyclomatic_complexity', 0),
                              reverse=True)[:20]
        
        for result in sorted_results:
            metrics = result['metrics']
            complexity = metrics.get('cyclomatic_complexity', 0)
            
            # Color code complexity
            if complexity > 20:
                complexity_str = f"[red]{complexity}[/red]"
            elif complexity > 10:
                complexity_str = f"[yellow]{complexity}[/yellow]"
            else:
                complexity_str = f"[green]{complexity}[/green]"
            
            table.add_row(
                Path(result['file']).name,
                result['language'],
                str(metrics.get('functions', 0)),
                str(metrics.get('classes', 0)),
                complexity_str,
                f"{result['size_kb']:.1f}"
            )
        
        console.print(table)


def _export_analysis_results(results: List[Dict[str, Any]], output: Path, format: str):
    """Export analysis results to file."""
    
    if format == "json":
        output.write_text(json.dumps(results, indent=2))
    elif format == "csv":
        import csv
        
        with output.open('w', newline='') as f:
            if results and results[0]['success']:
                # Get all possible field names
                fieldnames = set()
                for result in results:
                    if result['success']:
                        fieldnames.update(['file', 'language', 'size_kb', 'parse_time'])
                        fieldnames.update(result['metrics'].keys())
                
                fieldnames = sorted(fieldnames)
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                
                for result in results:
                    if result['success']:
                        row = {
                            'file': result['file'],
                            'language': result['language'],
                            'size_kb': result['size_kb'],
                            'parse_time': result.get('parse_time', 0)
                        }
                        row.update(result['metrics'])
                        writer.writerow(row)


# ========================================================================
# AST Display Commands
# ========================================================================

@app.command()
def ast(
    source: Optional[Path] = typer.Argument(None, help="Source file to parse"),
    code: Optional[str] = typer.Option(None, "--code", "-c", help="Inline code to parse"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Language (auto-detect if not specified)"),
    max_depth: int = typer.Option(4, "--depth", "-d", help="Maximum tree depth to display"),
    show_text: bool = typer.Option(True, "--text/--no-text", help="Show node text content"),
    show_metrics: bool = typer.Option(False, "--metrics", "-m", help="Show computed metrics"),
    format: str = typer.Option("tree", "--format", "-f", help="Output format: tree, json, sexp"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file")
):
    """Display AST structure with enhanced formatting and metrics."""
    
    if not source and not code:
        console.print("❌ [red]Provide either source file or --code[/red]")
        raise typer.Exit(1)
    
    try:
        # Parse input
        if source:
            code = source.read_text()
            if not language:
                parser = Parser.auto_detect(source)
            else:
                parser = Parser.for_language(language)
        else:
            language = language or "python"
            parser = Parser.for_language(language)
        
        with console.status("[spinner]Parsing AST..."):
            node = parser.parse(code)
        
        # Generate output
        if format == "json":
            result = node.export_json(
                mode="full",
                include_computed=show_metrics,
                indent=2
            )
        elif format == "sexp":
            result = node.export_sexp()
        else:  # tree format
            result = _format_ast_tree(node, max_depth, show_text, show_metrics)
        
        # Output
        if output:
            output.write_text(result)
            console.print(f"📄 AST written to [blue]{output}[/blue]")
        else:
            if format == "json":
                console.print(JSON(result))
            elif format == "sexp":
                console.print(Syntax(result, "lisp", theme="monokai"))
            else:
                console.print(result)
    
    except Exception as e:
        console.print(f"❌ [red]Error:[/red] {e}")
        raise typer.Exit(1)


def _format_ast_tree(node: TSNode, max_depth: int, show_text: bool, show_metrics: bool) -> str:
    """Format AST as rich tree structure."""
    # Create a console without color for capture
    from rich.console import Console
    plain_console = Console(force_terminal=False, width=150)
    
    tree = RichTree(f"{node.type_name}")
    
    if show_metrics:
        try:
            metrics = node.get_metrics()
            tree.label += f" (nodes: {metrics['total_nodes']}, complexity: {metrics['cyclomatic_complexity']})"
        except (AttributeError, KeyError):
            pass
    
    _add_tree_children(tree, node, max_depth, show_text, show_metrics, 0)
    
    # Render to string without ANSI codes
    with plain_console.capture() as capture:
        plain_console.print(tree)
    
    return capture.get()


def _add_tree_children(tree, node: TSNode, max_depth: int, show_text: bool, show_metrics: bool, depth: int):
    """Recursively add children to tree display."""
    if depth >= max_depth:
        if node.children:
            tree.add(f"... ({len(node.children)} more children)")
        return
    
    for child in node.children:
        if not child.is_named:
            continue
        
        label = child.type_name
        
        if show_text and child.text.strip():
            text = child.text.strip().replace("\n", " ")[:40]
            if len(text) == 40:
                text += "..."
            label += f": {text!r}"
        
        if show_metrics:
            try:
                descendant_count = len(list(child.descendants()))
                if descendant_count > 0:
                    label += f" ({descendant_count} nodes)"
            except (AttributeError, TypeError):
                pass
        
        child_tree = tree.add(label)
        _add_tree_children(child_tree, child, max_depth, show_text, show_metrics, depth + 1)

# ========================================================================
# Main CLI Runner
# ========================================================================

def run_cli():
    """Main CLI entry point with comprehensive error handling."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n⚠️  [yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"\n💥 [red]Unexpected error:[/red] {e}")
        console.print("[dim]Use --help for usage information[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    run_cli()
