# pydantree/cli/commands/batch.py
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn, MofNCompleteColumn
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.align import Align

from ...core.parsers import Parser, MultiLanguageParser#, LanguageRegistry
from ...core.profiler import PerformanceProfiler
from ...processing.batch import (
    BatchProcessor, ProcessingMode, ProcessingPriority, 
    discover_source_files, batch_processing_session
)
from ...export.engine import ExportEngine, ExportOptions, ExportFormat, OutputFormat, CompressionType

batch_app = typer.Typer(name="batch", help="High-performance batch processing operations")
console = Console()


@batch_app.command("process")
def batch_process(
    source_dir: Path = typer.Argument(..., help="Source directory to process"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file/directory"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Target language (auto-detect if not specified)"),
    format: str = typer.Option("jsonl", "--format", "-f", help="Output format: json, jsonl, csv, binary"),
    export_format: str = typer.Option("metrics", "--export", "-e", help="Export format: full, clean, metrics, minimal"),
    workers: int = typer.Option(4, "--workers", "-w", help="Number of parallel workers"),
    batch_size: int = typer.Option(100, "--batch-size", help="Files per batch"),
    mode: str = typer.Option("threaded", "--mode", "-m", help="Processing mode: sequential, threaded, process, async, hybrid"),
    compression: str = typer.Option("none", "--compression", "-c", help="Compression: none, gzip, lz4, zstd"),
    include_errors: bool = typer.Option(False, "--include-errors", help="Include files with parse errors"),
    max_files: Optional[int] = typer.Option(None, "--max-files", help="Maximum files to process"),
    exclude_patterns: Optional[str] = typer.Option(None, "--exclude", help="Comma-separated exclusion patterns"),
    streaming: bool = typer.Option(False, "--streaming", help="Use streaming for large datasets"),
    chunk_size: int = typer.Option(1000, "--chunk-size", help="Chunk size for streaming"),
    profile: bool = typer.Option(False, "--profile", help="Enable performance profiling"),
    save_profile: Optional[Path] = typer.Option(None, "--save-profile", help="Save performance profile to file"),
    baseline: Optional[Path] = typer.Option(None, "--baseline", help="Compare against performance baseline"),
    show_progress: bool = typer.Option(True, "--progress/--no-progress", help="Show progress indicators"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be processed without executing")
):
    """Process directories in batches with advanced options and performance monitoring."""
    
    if not source_dir.exists():
        console.print(f"❌ [red]Directory not found:[/red] {source_dir}")
        raise typer.Exit(1)
    
    # Validate mode
    try:
        processing_mode = ProcessingMode(mode)
    except ValueError:
        console.print(f"❌ [red]Invalid mode:[/red] {mode}. Choose from: sequential, threaded, process, async, hybrid")
        raise typer.Exit(1)
    
    # Setup profiler
    profiler = PerformanceProfiler(enabled=profile, track_memory=True)
    
    with profiler.profile('batch_command_setup'):
        # Discover files
        exclusions = exclude_patterns.split(',') if exclude_patterns else None
        
        if language:
            files = discover_source_files(source_dir, [language], exclude_patterns=exclusions)
        else:
            # Auto-discover all supported files
            supported_langs = LanguageRegistry.get_supported_languages()
            files = discover_source_files(source_dir, supported_langs, exclude_patterns=exclusions)
        
        if max_files:
            files = files[:max_files]
        
        if not files:
            console.print("❌ [red]No source files found[/red]")
            raise typer.Exit(1)
        
        console.print(f"📁 Found [green]{len(files):,}[/green] files to process")
        
        if dry_run:
            _show_dry_run_summary(files, processing_mode, workers, batch_size)
            return
    
    # Setup parser
    if language:
        parser = Parser.for_language(language, profiler=profiler)
        console.print(f"🔧 Using [blue]{language}[/blue] parser")
    else:
        supported_languages = LanguageRegistry.get_supported_languages()[:10]  # Limit for performance
        parser = MultiLanguageParser(supported_languages, profiler=profiler)
        console.print(f"🔧 Using multi-language parser ([blue]{len(supported_languages)} languages[/blue])")
    
    # Process files
    start_time = time.time()
    
    with batch_processing_session(
        parser=parser,
        batch_size=batch_size,
        mode=processing_mode,
        enable_profiling=profile
    ) as processor:
        
        processor.max_workers = workers
        
        # Create progress callback
        progress_callback = None
        processed_count = 0
        
        def update_progress(current: int, total: int):
            nonlocal processed_count
            processed_count = current
        
        if show_progress:
            progress_callback = update_progress
        
        # Process files with progress tracking
        all_results = []
        
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
                
                for batch_result in processor.process_files(
                    files,
                    include_metrics=True,
                    progress_callback=progress_callback
                ):
                    all_results.append(batch_result)
                    progress.update(task, completed=processed_count)
        else:
            # Process without progress bar
            all_results = list(processor.process_files(files, include_metrics=True))
    
    processing_time = time.time() - start_time
    
    # Aggregate results
    total_files = sum(len(r.files) for r in all_results)
    successful = sum(r.success_count for r in all_results)
    failed = sum(r.error_count for r in all_results)
    
    # Export results if requested
    if output:
        with profiler.profile('export_results'):
            _export_batch_results(all_results, output, format, export_format, compression, streaming, chunk_size)
        console.print(f"📄 Results exported to [blue]{output}[/blue]")
    
    # Display summary
    _display_batch_summary(all_results, processing_time, profiler, profile)
    
    # Handle profiling output
    if save_profile:
        profiler.save_report(save_profile)
        console.print(f"📊 Performance profile saved to [blue]{save_profile}[/blue]")
    
    if baseline:
        comparison = profiler.compare_with_baseline(baseline)
        _display_performance_comparison(comparison)


def _show_dry_run_summary(files: List[Path], mode: ProcessingMode, workers: int, batch_size: int):
    """Show what would be processed in dry run mode."""
    
    # Analyze file distribution
    lang_distribution = {}
    size_distribution = {'small': 0, 'medium': 0, 'large': 0}
    total_size = 0
    
    for file_path in files:
        # Language detection
        lang = LanguageRegistry.detect_language(file_path) or 'unknown'
        lang_distribution[lang] = lang_distribution.get(lang, 0) + 1
        
        # Size analysis
        try:
            size = file_path.stat().st_size
            total_size += size
            
            if size < 10_000:  # < 10KB
                size_distribution['small'] += 1
            elif size < 100_000:  # < 100KB  
                size_distribution['medium'] += 1
            else:
                size_distribution['large'] += 1
        except OSError:
            pass
    
    # Calculate batches
    num_batches = (len(files) + batch_size - 1) // batch_size
    
    # Create summary panel
    summary_info = f"""[green]{len(files):,}[/green] files would be processed
[blue]{num_batches:,}[/blue] batches with size {batch_size}
[yellow]{workers}[/yellow] workers in [magenta]{mode.value}[/magenta] mode
[cyan]{total_size / 1024 / 1024:.1f} MB[/cyan] total size"""
    
    console.print(Panel(summary_info, title="Dry Run Summary"))
    
    # Language distribution table
    if lang_distribution:
        lang_table = Table(title="Language Distribution", show_lines=False)
        lang_table.add_column("Language", style="blue")
        lang_table.add_column("Count", justify="right", style="green")
        lang_table.add_column("Percentage", justify="right", style="cyan")
        
        for lang, count in sorted(lang_distribution.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(files)) * 100
            lang_table.add_row(lang, f"{count:,}", f"{percentage:.1f}%")
        
        console.print(lang_table)


def _export_batch_results(results: List, output: Path, format: str, export_format: str, 
                         compression: str, streaming: bool, chunk_size: int):
    """Export batch results with specified options."""
    
    # Flatten all file results
    all_file_results = []
    for batch_result in results:
        all_file_results.extend(batch_result.files)
    
    # Setup export options
    export_options = ExportOptions(
        format=ExportFormat(export_format),
        output_format=OutputFormat(format),
        compression=CompressionType(compression),
        streaming=streaming,
        chunk_size=chunk_size,
        include_computed=True
    )
    
    # Export using engine
    exporter = ExportEngine(all_file_results)
    exporter.export_to_file(output, export_options)


def _display_batch_summary(results: List, processing_time: float, profiler: PerformanceProfiler, show_profiling: bool):
    """Display comprehensive batch processing summary."""
    
    # Aggregate statistics
    total_files = sum(len(r.files) for r in results)
    successful = sum(r.success_count for r in results)
    failed = sum(r.error_count for r in results)
    total_processing_time = sum(r.batch_time for r in results)
    
    # Language distribution
    lang_distribution = {}
    for batch_result in results:
        for file_result in batch_result.files:
            if file_result.success and file_result.language:
                lang = file_result.language
                lang_distribution[lang] = lang_distribution.get(lang, 0) + 1
    
    # Performance metrics
    avg_file_time = total_processing_time / total_files if total_files > 0 else 0
    files_per_second = total_files / processing_time if processing_time > 0 else 0
    success_rate = (successful / total_files) * 100 if total_files > 0 else 0
    
    # Summary panel
    summary_text = f"""[green]{successful:,}[/green] files processed successfully
[red]{failed:,}[/red] files failed ([yellow]{success_rate:.1f}%[/yellow] success rate)
[blue]{processing_time:.1f}s[/blue] total time ([cyan]{files_per_second:.1f}[/cyan] files/sec)
[magenta]{len(results)}[/magenta] batches processed"""
    
    console.print(Panel(summary_text, title="Batch Processing Summary"))
    
    # Language distribution
    if lang_distribution:
        lang_items = []
        for lang, count in sorted(lang_distribution.items(), key=lambda x: x[1], reverse=True)[:6]:
            percentage = (count / successful) * 100 if successful > 0 else 0
            lang_items.append(f"[blue]{lang}[/blue]: {count} ([dim]{percentage:.1f}%[/dim])")
        
        lang_panel = Panel('\n'.join(lang_items), title="Language Distribution")
        console.print(lang_panel)
    
    # Performance details
    if show_profiling:
        perf_report = profiler.get_detailed_report()
        
        perf_table = Table(title="Performance Breakdown", show_lines=False)
        perf_table.add_column("Operation", style="cyan")
        perf_table.add_column("Time", justify="right", style="green")
        perf_table.add_column("Memory", justify="right", style="blue")
        
        for metric in perf_report['detailed_metrics'][:5]:  # Top 5
            perf_table.add_row(
                metric['operation'],
                metric['duration'],
                f"{metric.get('memory', {}).get('delta', 0):.1f}MB"
            )
        
        console.print(perf_table)


def _display_performance_comparison(comparison: Dict[str, Any]):
    """Display performance comparison with baseline."""
    
    assessment = comparison['overall_assessment']
    
    if assessment == 'performance_regression':
        status_text = "[red]⚠️  Performance regression detected[/red]"
    elif assessment == 'performance_improvement':
        status_text = "[green]✅ Performance improvement detected[/green]"
    else:
        status_text = "[blue]📊 Performance is stable[/blue]"
    
    console.print(Panel(status_text, title="Baseline Comparison"))
    
    # Show significant changes
    changes = comparison.get('performance_changes', {})
    if changes:
        changes_table = Table(title="Performance Changes", show_lines=False)
        changes_table.add_column("Operation", style="cyan")
        changes_table.add_column("Change", justify="right", style="yellow")
        changes_table.add_column("Status", style="white")
        
        for op, change_data in list(changes.items())[:5]:
            status_style = {
                'regression': 'red',
                'improvement': 'green',
                'stable': 'blue'
            }.get(change_data['status'], 'white')
            
            changes_table.add_row(
                op,
                change_data['change_percent'],
                f"[{status_style}]{change_data['status']}[/{status_style}]"
            )
        
        console.print(changes_table)


@batch_app.command("discover")
def discover_files(
    source_dir: Path = typer.Argument(..., help="Source directory to scan"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Target language filter"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r", help="Search recursively"),
    include_hidden: bool = typer.Option(False, "--hidden", help="Include hidden files"),
    max_size_mb: Optional[int] = typer.Option(None, "--max-size", help="Maximum file size in MB"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save file list to output"),
    show_details: bool = typer.Option(False, "--details", "-d", help="Show detailed file information")
):
    """Discover and analyze source files in directories."""
    
    if not source_dir.exists():
        console.print(f"❌ [red]Directory not found:[/red] {source_dir}")
        raise typer.Exit(1)
    
    # Discover files
    languages = [language] if language else None
    files = discover_source_files(
        source_dir, 
        languages=languages,
        include_hidden=include_hidden,
        max_size_mb=max_size_mb
    )
    
    if not files:
        console.print("❌ [red]No source files found[/red]")
        return
    
    console.print(f"📁 Discovered [green]{len(files):,}[/green] source files")
    
    if show_details:
        _show_discovery_details(files)
    
    if output:
        file_list = [str(f) for f in files]
        output.write_text('\n'.join(file_list))
        console.print(f"📄 File list saved to [blue]{output}[/blue]")


def _show_discovery_details(files: List[Path]):
    """Show detailed file discovery analysis."""
    
    # Analyze files
    lang_stats = {}
    size_stats = {'total_size': 0, 'avg_size': 0, 'size_distribution': {}}
    
    for file_path in files:
        # Language detection
        lang = LanguageRegistry.detect_language(file_path) or 'unknown'
        if lang not in lang_stats:
            lang_stats[lang] = {'count': 0, 'total_size': 0}
        lang_stats[lang]['count'] += 1
        
        # Size analysis
        try:
            size = file_path.stat().st_size
            lang_stats[lang]['total_size'] += size
            size_stats['total_size'] += size
            
            # Size categories
            if size < 1000:
                category = 'tiny'
            elif size < 10_000:
                category = 'small'
            elif size < 100_000:
                category = 'medium'
            else:
                category = 'large'
            
            size_stats['size_distribution'][category] = size_stats['size_distribution'].get(category, 0) + 1
            
        except OSError:
            pass
    
    size_stats['avg_size'] = size_stats['total_size'] / len(files) if files else 0
    
    # Display language statistics
    lang_table = Table(title="Language Analysis", show_lines=True)
    lang_table.add_column("Language", style="blue")
    lang_table.add_column("Files", justify="right", style="green") 
    lang_table.add_column("Total Size", justify="right", style="cyan")
    lang_table.add_column("Avg Size", justify="right", style="yellow")
    
    for lang, stats in sorted(lang_stats.items(), key=lambda x: x[1]['count'], reverse=True):
        avg_size = stats['total_size'] / stats['count'] if stats['count'] > 0 else 0
        lang_table.add_row(
            lang,
            f"{stats['count']:,}",
            f"{stats['total_size'] / 1024:.1f} KB",
            f"{avg_size / 1024:.1f} KB"
        )
    
    console.print(lang_table)
    
    # Display size distribution
    size_items = []
    for category, count in size_stats['size_distribution'].items():
        percentage = (count / len(files)) * 100
        size_items.append(f"[blue]{category}[/blue]: {count} ([dim]{percentage:.1f}%[/dim])")
    
    size_panel = Panel(
        '\n'.join(size_items),
        title=f"Size Distribution (Total: {size_stats['total_size'] / 1024 / 1024:.1f} MB)"
    )
    console.print(size_panel)
