# examples/06_export_examples.py

"""Export functionality examples for various output formats."""

from pathlib import Path
from pydantree import Parser, from_tree
from pydantree.export.engine import (
    ExportEngine, ExportOptions, ExportFormat, 
    OutputFormat, CompressionType
)
from pydantree.processing.batch import BatchProcessor, ProcessingMode

# Example 1: Basic export formats
def basic_export_formats():
    """Export AST data in different formats."""
    
    parser = Parser.for_language("python")
    code = '''
def calculate_stats(data):
    """Calculate basic statistics."""
    if not data:
        return {}
    
    total = sum(data)
    count = len(data)
    mean = total / count
    
    sorted_data = sorted(data)
    median = sorted_data[count // 2]
    
    return {
        'count': count,
        'sum': total,
        'mean': mean,
        'median': median,
        'min': min(data),
        'max': max(data)
    }

class DataAnalyzer:
    def __init__(self):
        self.results = []
    
    def analyze(self, dataset):
        stats = calculate_stats(dataset)
        self.results.append(stats)
        return stats
'''
    
    ast_root = parser.parse(code)
    
    # Create export engine
    engine = ExportEngine(ast_root)
    
    # Export to different formats
    output_dir = Path("exports")
    output_dir.mkdir(exist_ok=True)
    
    formats = [
        (OutputFormat.JSON, ExportFormat.FULL),
        (OutputFormat.JSON, ExportFormat.CLEAN),
        (OutputFormat.JSON, ExportFormat.MINIMAL),
        (OutputFormat.JSONL, ExportFormat.METRICS),
        (OutputFormat.CSV, ExportFormat.METRICS),
    ]
    
    for output_format, export_format in formats:
        options = ExportOptions(
            format=export_format,
            output_format=output_format,
            include_computed=True
        )
        
        ext = {
            OutputFormat.JSON: '.json',
            OutputFormat.JSONL: '.jsonl',
            OutputFormat.CSV: '.csv'
        }[output_format]
        
        output_path = output_dir / f"ast_{export_format.value}{ext}"
        stats = engine.export_to_file(output_path, options)
        
        size_kb = output_path.stat().st_size / 1024
        print(f"{export_format.value:8} -> {output_format.value:4}: {size_kb:6.1f}KB")
    
    return engine

# Example 2: Compression and streaming
def compression_streaming():
    """Demonstrate compression and streaming exports."""
    
    # Create larger dataset
    parser = Parser.for_language("python")
    
    # Generate complex code
    code_parts = []
    for i in range(50):  # Multiple functions and classes
        code_parts.append(f'''
def function_{i}(x, y=None):
    """Function {i} with parameters."""
    if y is None:
        y = {i}
    
    result = x + y
    for j in range({i % 5 + 1}):
        result *= 1.1
    
    return result

class Class{i}:
    """Class {i} for testing."""
    
    def __init__(self, value={i}):
        self.value = value
        self.data = list(range({i * 2}))
    
    def process(self):
        return [self.value + x for x in self.data]
''')
    
    large_code = '\n'.join(code_parts)
    ast_root = parser.parse(large_code)
    nodegroup = from_tree(ast_root)
    
    engine = ExportEngine(nodegroup)
    output_dir = Path("compression_test")
    output_dir.mkdir(exist_ok=True)
    
    # Test different compression types
    compressions = [
        CompressionType.NONE,
        CompressionType.GZIP,
        CompressionType.LZ4,
        CompressionType.ZSTD
    ]
    
    print("Compression comparison:")
    print(f"{'Type':<8} {'Size (KB)':<10} {'Ratio':<8} {'Time (s)':<10}")
    print("-" * 40)
    
    for compression in compressions:
        options = ExportOptions(
            format=ExportFormat.FULL,
            output_format=OutputFormat.JSON,
            compression=compression,
            indent=2
        )
        
        filename = f"large_ast_{compression.value}.json"
        if compression != CompressionType.NONE:
            filename += f".{compression.value}"
        
        output_path = output_dir / filename
        
        import time
        start_time = time.time()
        stats = engine.export_to_file(output_path, options)
        export_time = time.time() - start_time
        
        size_kb = output_path.stat().st_size / 1024
        ratio = stats.get('compression_ratio', 1.0)
        
        print(f"{compression.value:<8} {size_kb:<10.1f} {ratio:<8.2f} {export_time:<10.3f}")
    
    # Streaming export
    print("\nStreaming export...")
    stream_options = ExportOptions(
        format=ExportFormat.CLEAN,
        output_format=OutputFormat.JSONL,
        streaming=True,
        chunk_size=100
    )
    
    stream_output = output_dir / "streamed_ast.jsonl"
    chunk_count = 0
    
    for progress in engine.stream_export(stream_output, stream_options):
        chunk_count += 1
        processed = progress['total_processed']
        print(f"  Chunk {chunk_count}: {processed} items processed")
    
    return engine

# Example 3: Batch results export
def batch_results_export():
    """Export batch processing results."""
    
    # Create test files
    test_dir = Path("batch_export_test")
    test_dir.mkdir(exist_ok=True)
    
    test_files = []
    for i in range(10):
        file_path = test_dir / f"module_{i}.py"
        code = f'''
"""Module {i} for batch testing."""

import math
import json

def func_{i}(data):
    """Process data in module {i}."""
    if not data:
        return []
    
    results = []
    for item in data:
        if isinstance(item, (int, float)):
            processed = item * {i + 1}
            if processed > 100:
                processed = math.sqrt(processed)
            results.append(processed)
        elif isinstance(item, str):
            results.append(f"module_{i}_{item}")
        else:
            results.append(str(item))
    
    return results

class Processor{i}:
    """Data processor for module {i}."""
    
    def __init__(self):
        self.config = {{
            "multiplier": {i + 1},
            "prefix": "mod_{i}_"
        }}
    
    def process_batch(self, items):
        return [self.process_item(item) for item in items]
    
    def process_item(self, item):
        return f"{{self.config['prefix']}}{{item}}"

# Module constants
MODULE_ID = {i}
VERSION = "1.{i}.0"
'''
        file_path.write_text(code)
        test_files.append(file_path)
    
    # Process files in batch
    parser = Parser.for_language("python")
    processor = BatchProcessor(
        parser=parser,
        batch_size=3,
        mode=ProcessingMode.THREADED
    )
    
    batch_results = list(processor.process_files(test_files, include_metrics=True))
    
    # Export batch results
    output_dir = Path("batch_exports")
    output_dir.mkdir(exist_ok=True)
    
    # Export individual batch results
    for i, batch_result in enumerate(batch_results):
        engine = ExportEngine(batch_result)
        
        # Summary export
        summary_options = ExportOptions(
            format=ExportFormat.SUMMARY,
            output_format=OutputFormat.JSON,
            include_computed=True
        )
        
        summary_path = output_dir / f"batch_{i}_summary.json"
        engine.export_to_file(summary_path, summary_options)
        
        # Detailed metrics export
        metrics_options = ExportOptions(
            format=ExportFormat.METRICS,
            output_format=OutputFormat.CSV
        )
        
        metrics_path = output_dir / f"batch_{i}_metrics.csv"
        engine.export_to_file(metrics_path, metrics_options)
    
    # Combine all results
    all_results = []
    for batch_result in batch_results:
        all_results.extend(batch_result.files)
    
    combined_engine = ExportEngine(all_results)
    
    # Export combined results with compression
    combined_options = ExportOptions(
        format=ExportFormat.METRICS,
        output_format=OutputFormat.JSONL,
        compression=CompressionType.LZ4,
        streaming=True
    )
    
    combined_path = output_dir / "all_results.jsonl.lz4"
    stats = combined_engine.export_to_file(combined_path, combined_options)
    
    print(f"Batch export results:")
    print(f"  Processed {len(all_results)} files")
    print(f"  Combined size: {combined_path.stat().st_size / 1024:.1f}KB")
    print(f"  Compression ratio: {stats.get('compression_ratio', 1.0):.2f}")
    
    return batch_results, all_results

# Example 4: Custom export filters
def custom_export_filters():
    """Export with custom filtering and transformation."""
    
    parser = Parser.for_language("python")
    code = '''
import asyncio
from typing import List, Dict, Optional

async def fetch_data(url: str) -> Dict:
    """Fetch data from URL asynchronously."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

class APIClient:
    """Async API client with caching."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self._cache: Dict[str, Dict] = {}
    
    async def get(self, endpoint: str, use_cache: bool = True) -> Optional[Dict]:
        """GET request with optional caching."""
        if use_cache and endpoint in self._cache:
            return self._cache[endpoint]
        
        url = f"{self.base_url}/{endpoint}"
        data = await fetch_data(url)
        
        if use_cache:
            self._cache[endpoint] = data
        
        return data
    
    async def post(self, endpoint: str, payload: Dict) -> Dict:
        """POST request."""
        url = f"{self.base_url}/{endpoint}"
        # Implementation details...
        return {"status": "success"}
    
    def clear_cache(self):
        """Clear the cache."""
        self._cache.clear()

# Global configuration
API_CONFIG = {
    "timeout": 30,
    "retries": 3,
    "base_url": "https://api.example.com"
}
'''
    
    ast_root = parser.parse(code)
    nodegroup = from_tree(ast_root)
    
    # Filter for only function definitions and classes
    functions_and_classes = nodegroup.filter_type({
        "function_definition", 
        "class_definition", 
        "async_function_definition"
    })
    
    print(f"Filtered {len(functions_and_classes)} functions and classes")
    
    # Create custom export options
    custom_options = ExportOptions(
        format=ExportFormat.CLEAN,  # Clean format without full tree
        output_format=OutputFormat.JSON,
        include_spans=True,
        include_computed=True,
        indent=2
    )
    
    # Export filtered nodes
    engine = ExportEngine(functions_and_classes)
    output_path = Path("custom_filtered.json")
    stats = engine.export_to_file(output_path, custom_options)
    
    print(f"Exported {stats['items_processed']} filtered items")
    
    # Export to string for in-memory processing
    json_string = engine.export_to_string(custom_options)
    print(f"JSON string length: {len(json_string)} characters")
    
    # Custom metrics export
    metrics_data = []
    for node in functions_and_classes:
        metrics = node.get_metrics()
        
        # Extract specific metrics
        custom_metrics = {
            'name': node.child_by_field_name('name').text if node.child_by_field_name('name') else 'anonymous',
            'type': node.type_name,
            'complexity': metrics['cyclomatic_complexity'],
            'lines': metrics['line_count'],
            'nodes': metrics['total_nodes'],
            'start_line': node.start_point.row + 1,
            'is_async': 'async' in node.type_name
        }
        metrics_data.append(custom_metrics)
    
    # Export custom metrics
    metrics_engine = ExportEngine(metrics_data)
    metrics_options = ExportOptions(
        output_format=OutputFormat.CSV
    )
    
    metrics_path = Path("custom_metrics.csv")
    metrics_engine.export_to_file(metrics_path, metrics_options)
    
    print(f"Custom metrics exported to {metrics_path}")
    
    return engine, metrics_data

# Example 5: Binary and performance exports
def binary_performance_exports():
    """High-performance binary exports."""
    
    # Generate large dataset
    parser = Parser.for_language("python")
    
    # Create substantial code base
    modules = []
    for module_idx in range(20):
        code_lines = [f'"""Module {module_idx} - Generated for performance testing."""']
        
        for class_idx in range(10):
            class_name = f"Class{module_idx}_{class_idx}"
            code_lines.extend([
                f"",
                f"class {class_name}:",
                f'    """Class {class_idx} in module {module_idx}."""',
                f"    ",
                f"    def __init__(self, value={class_idx}):",
                f"        self.value = value",
                f"        self.data = [i * {class_idx} for i in range({class_idx + 1})]",
            ])
            
            for method_idx in range(5):
                method_name = f"method_{method_idx}"
                code_lines.extend([
                    f"    ",
                    f"    def {method_name}(self, param={method_idx}):",
                    f'        """Method {method_idx} implementation."""',
                    f"        result = self.value + param",
                    f"        for i in range({method_idx + 1}):",
                    f"            result += i",
                    f"        return result",
                ])
        
        modules.append('\n'.join(code_lines))
    
    # Parse all modules
    all_nodes = []
    for i, code in enumerate(modules):
        print(f"Parsing module {i + 1}/{len(modules)}")
        ast_root = parser.parse(code)
        nodegroup = from_tree(ast_root)
        all_nodes.extend(nodegroup.to_list())
    
    print(f"Total nodes for export: {len(all_nodes):,}")
    
    # Performance comparison
    output_dir = Path("performance_exports")
    output_dir.mkdir(exist_ok=True)
    
    export_configs = [
        ("JSON", OutputFormat.JSON, CompressionType.NONE),
        ("JSON+GZIP", OutputFormat.JSON, CompressionType.GZIP),
        ("JSONL", OutputFormat.JSONL, CompressionType.NONE),
        ("JSONL+LZ4", OutputFormat.JSONL, CompressionType.LZ4),
        ("Binary", OutputFormat.BINARY, CompressionType.NONE),
        ("Binary+ZSTD", OutputFormat.BINARY, CompressionType.ZSTD),
    ]
    
    print(f"\nPerformance Export Comparison:")
    print(f"{'Format':<12} {'Size (MB)':<10} {'Time (s)':<10} {'Rate (MB/s)':<12}")
    print("-" * 50)
    
    for name, output_format, compression in export_configs:
        engine = ExportEngine(all_nodes)
        options = ExportOptions(
            format=ExportFormat.MINIMAL,  # Fastest export format
            output_format=output_format,
            compression=compression,
            streaming=True,
            chunk_size=1000
        )
        
        output_path = output_dir / f"perf_test_{name.lower().replace('+', '_')}"
        
        import time
        start_time = time.time()
        stats = engine.export_to_file(output_path, options)
        export_time = time.time() - start_time
        
        size_mb = output_path.stat().st_size / (1024 * 1024)
        rate = size_mb / export_time if export_time > 0 else 0
        
        print(f"{name:<12} {size_mb:<10.2f} {export_time:<10.3f} {rate:<12.1f}")
    
    return all_nodes

if __name__ == "__main__":
    print("=== Export Functionality Examples ===\n")
    
    print("1. Basic export formats:")
    basic_export_formats()
    
    print("\n2. Compression and streaming:")
    compression_streaming()
    
    print("\n3. Batch results export:")
    batch_results_export()
    
    print("\n4. Custom export filters:")
    custom_export_filters()
    
    print("\n5. Binary and performance exports:")
    binary_performance_exports()
