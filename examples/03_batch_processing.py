# examples/03_batch_processing.py

"""Batch processing examples for handling multiple files efficiently."""

import time
from pathlib import Path
from pydantree import Parser, get_supported_languages
from pydantree.core.parsers import MultiLanguageParser
from pydantree.processing.batch import (
    BatchProcessor, ProcessingMode, ProcessingPriority,
    discover_source_files, batch_processing_session
)
from pydantree.core.profiler import PerformanceProfiler

# Example 1: Basic batch processing
def basic_batch_processing():
    """Process multiple files in a batch."""
    
    # Create test files
    test_files = []
    base_dir = Path("test_files")
    base_dir.mkdir(exist_ok=True)
    
    # Create sample Python files
    for i in range(5):
        file_path = base_dir / f"module_{i}.py"
        code = f'''
"""Module {i} - Sample code for testing."""

def function_{i}(x):
    """Process data for module {i}."""
    result = x * {i + 1}
    if result > 10:
        return result ** 2
    return result

class Class{i}:
    def __init__(self):
        self.value = {i}
    
    def process(self, data):
        return [item + self.value for item in data]

# Global variable
MODULE_{i}_CONSTANT = {i * 10}
'''
        file_path.write_text(code)
        test_files.append(file_path)
    
    # Create batch processor
    parser = Parser.for_language("python")
    profiler = PerformanceProfiler(enabled=True)
    
    processor = BatchProcessor(
        parser=parser,
        batch_size=2,  # Small batches for demo
        profiler=profiler,
        max_workers=2,
        mode=ProcessingMode.THREADED
    )
    
    print("Processing files in batches...")
    start_time = time.time()
    
    results = []
    for batch_result in processor.process_files(test_files, include_metrics=True):
        print(f"Batch completed: {batch_result.success_count}/{len(batch_result.files)} successful")
        results.append(batch_result)
    
    total_time = time.time() - start_time
    
    # Analyze results
    total_files = sum(len(batch.files) for batch in results)
    successful_files = sum(batch.success_count for batch in results)
    
    print(f"\nBatch Processing Summary:")
    print(f"  Total files: {total_files}")
    print(f"  Successful: {successful_files}")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Files/second: {total_files/total_time:.1f}")
    
    # Show profiler results
    prof_stats = profiler.get_summary()
    print(f"  Operations profiled: {prof_stats['total_operations']}")
    
    return results, profiler

# Example 2: Directory discovery and processing
def directory_processing():
    """Discover and process all source files in a directory."""
    
    # Create a complex directory structure
    project_dir = Path("sample_project")
    project_dir.mkdir(exist_ok=True)
    
    # Python package
    (project_dir / "src").mkdir(exist_ok=True)
    (project_dir / "src" / "__init__.py").write_text("")
    (project_dir / "src" / "main.py").write_text('''
import sys
from pathlib import Path

def main():
    """Main entry point."""
    print("Hello, world!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
''')
    
    # Tests
    (project_dir / "tests").mkdir(exist_ok=True)
    (project_dir / "tests" / "test_main.py").write_text('''
import unittest
from src.main import main

class TestMain(unittest.TestCase):
    def test_main_returns_zero(self):
        result = main()
        self.assertEqual(result, 0)
''')
    
    # Config files
    (project_dir / "setup.py").write_text('''
from setuptools import setup, find_packages

setup(
    name="sample-project",
    version="0.1.0",
    packages=find_packages(),
)
''')
    
    # Discover files
    discovered_files = discover_source_files(
        project_dir,
        languages=["python"],
        include_hidden=False,
        max_size_mb=10
    )
    
    print(f"Discovered {len(discovered_files)} Python files:")
    for file_path in discovered_files:
        rel_path = file_path.relative_to(project_dir)
        size = file_path.stat().st_size
        print(f"  {rel_path} ({size} bytes)")
    
    # Process with multi-language parser
    parser = MultiLanguageParser(["python"])
    
    with batch_processing_session(
        parser=parser,
        batch_size=10,
        mode=ProcessingMode.THREADED,
        enable_profiling=True
    ) as processor:
        
        batch_results = list(processor.process_files(
            discovered_files,
            include_metrics=True
        ))
    
    return batch_results, discovered_files

# Example 3: Different processing modes
def compare_processing_modes():
    """Compare different batch processing modes."""
    
    # Create test data
    test_dir = Path("mode_test")
    test_dir.mkdir(exist_ok=True)
    
    files = []
    for i in range(10):
        file_path = test_dir / f"file_{i:02d}.py"
        # Create files of varying complexity
        complexity = i % 3 + 1
        code_lines = []
        
        for j in range(complexity * 10):
            if j % 4 == 0:
                code_lines.append(f"def func_{i}_{j}():")
                code_lines.append(f"    return {j}")
            elif j % 4 == 1:
                code_lines.append(f"class Class_{i}_{j}:")
                code_lines.append(f"    value = {j}")
            else:
                code_lines.append(f"var_{i}_{j} = {j}")
        
        file_path.write_text("\n".join(code_lines))
        files.append(file_path)
    
    parser = Parser.for_language("python")
    modes = [
        ProcessingMode.SEQUENTIAL,
        ProcessingMode.THREADED,
        ProcessingMode.PROCESS,
        ProcessingMode.HYBRID
    ]
    
    results = {}
    
    for mode in modes:
        print(f"\nTesting {mode.value} mode...")
        
        try:
            profiler = PerformanceProfiler(enabled=True)
            processor = BatchProcessor(
                parser=parser,
                batch_size=3,
                profiler=profiler,
                max_workers=2,
                mode=mode
            )
            
            start_time = time.time()
            batch_results = list(processor.process_files(files, include_metrics=True))
            processing_time = time.time() - start_time
            
            total_files = sum(len(batch.files) for batch in batch_results)
            successful = sum(batch.success_count for batch in batch_results)
            
            results[mode.value] = {
                'time': processing_time,
                'files': total_files,
                'successful': successful,
                'throughput': total_files / processing_time if processing_time > 0 else 0
            }
            
            print(f"  Processed {successful}/{total_files} files in {processing_time:.2f}s")
            print(f"  Throughput: {results[mode.value]['throughput']:.1f} files/sec")
            
        except Exception as e:
            print(f"  Failed: {e}")
            results[mode.value] = {'error': str(e)}
    
    # Compare results
    print(f"\nPerformance Comparison:")
    print(f"{'Mode':<12} {'Time':<8} {'Files':<6} {'Throughput':<12}")
    print("-" * 40)
    
    for mode_name, stats in results.items():
        if 'error' not in stats:
            print(f"{mode_name:<12} {stats['time']:<8.2f} {stats['files']:<6} {stats['throughput']:<12.1f}")
        else:
            print(f"{mode_name:<12} ERROR: {stats['error']}")
    
    return results

# Example 4: Priority-based processing
def priority_processing():
    """Process files with different priorities."""
    
    # Create files with different priorities
    priority_dir = Path("priority_test")
    priority_dir.mkdir(exist_ok=True)
    
    file_priorities = [
        ("critical_module.py", ProcessingPriority.CRITICAL),
        ("important_utils.py", ProcessingPriority.HIGH),
        ("helper_functions.py", ProcessingPriority.NORMAL),
        ("optional_extras.py", ProcessingPriority.LOW),
    ]
    
    files = []
    for filename, priority in file_priorities:
        file_path = priority_dir / filename
        code = f'''
# {filename} - Priority: {priority.name}

def process_with_priority():
    """Function with {priority.name} priority."""
    return "{priority.name}_result"

priority_level = "{priority.name}"
'''
        file_path.write_text(code)
        files.append((file_path, priority))
    
    parser = Parser.for_language("python")
    processor = BatchProcessor(
        parser=parser,
        batch_size=2,
        priority_queue_enabled=True
    )
    
    # Define priority function
    def get_file_priority(file_path: Path) -> ProcessingPriority:
        for path, priority in files:
            if path == file_path:
                return priority
        return ProcessingPriority.NORMAL
    
    # Process with priorities
    file_paths = [path for path, _ in files]
    
    print("Processing files by priority...")
    batch_results = list(processor.process_directory(
        priority_dir,
        recursive=False,
        priority_func=get_file_priority
    ))
    
    # Show processing order
    for i, batch_result in enumerate(batch_results):
        print(f"\nBatch {i + 1}:")
        for file_result in batch_result.files:
            rel_path = file_result.path.name
            print(f"  {rel_path} - {file_result.success}")
    
    return batch_results

# Example 5: Error handling and recovery
def error_handling():
    """Demonstrate error handling in batch processing."""
    
    error_test_dir = Path("error_test")
    error_test_dir.mkdir(exist_ok=True)
    
    # Create mix of valid and invalid files
    test_cases = [
        ("valid.py", "def valid_function():\n    return True"),
        ("syntax_error.py", "def invalid_function(\n    # Missing closing parenthesis"),
        ("empty.py", ""),
        ("large_file.py", "x = 1\n" * 10000),  # Large but valid
        ("binary.py", b"\x00\x01\x02\x03"),  # Binary content
    ]
    
    for filename, content in test_cases:
        file_path = error_test_dir / filename
        if isinstance(content, bytes):
            file_path.write_bytes(content)
        else:
            file_path.write_text(content)
    
    parser = Parser.for_language("python")
    profiler = PerformanceProfiler(enabled=True)
    
    processor = BatchProcessor(
        parser=parser,
        batch_size=2,
        profiler=profiler
    )
    
    # Process all files including problematic ones
    files = list(error_test_dir.glob("*.py"))
    batch_results = list(processor.process_files(files, include_metrics=True))
    
    print("Error Handling Results:")
    
    total_processed = 0
    total_successful = 0
    total_failed = 0
    
    for batch_result in batch_results:
        for file_result in batch_result.files:
            total_processed += 1
            filename = file_result.path.name
            
            if file_result.success:
                total_successful += 1
                metrics = file_result.metrics or {}
                node_count = metrics.get('total_nodes', 0)
                print(f"  ✓ {filename}: {node_count} nodes")
            else:
                total_failed += 1
                error_msg = file_result.error or "Unknown error"
                print(f"  ✗ {filename}: {error_msg}")
    
    print(f"\nSummary: {total_successful} successful, {total_failed} failed out of {total_processed}")
    
    return batch_results

if __name__ == "__main__":
    print("=== Batch Processing Examples ===\n")
    
    print("1. Basic batch processing:")
    basic_batch_processing()
    
    print("\n2. Directory processing:")
    directory_processing()
    
    print("\n3. Compare processing modes:")
    compare_processing_modes()
    
    print("\n4. Priority processing:")
    priority_processing()
    
    print("\n5. Error handling:")
    error_handling()
