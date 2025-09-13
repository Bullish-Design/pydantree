# examples/08_advanced_integrations.py

"""Advanced integration examples combining multiple Pydantree features."""

from pathlib import Path
from pydantree import Parser, from_tree, get_language
from pydantree.processing.batch import BatchProcessor, ProcessingMode
from pydantree.export.engine import ExportEngine, ExportOptions, OutputFormat, ExportFormat
from pydantree.graph.builder import GraphBuilder, PatternMatcher
from pydantree.core.profiler import PerformanceProfiler

# Example 1: Complete code analysis pipeline
def code_analysis_pipeline():
    """Complete analysis pipeline combining parsing, metrics, and export."""
    
    # Sample project structure
    project_dir = Path("sample_project")
    project_dir.mkdir(exist_ok=True)
    
    # Create realistic Python project
    files = {
        "main.py": '''
"""Main application entry point."""
import asyncio
from typing import List, Dict
from data_processor import DataProcessor
from utils import validate_config

async def main():
    """Run the main application."""
    config = load_config("config.json")
    if not validate_config(config):
        raise ValueError("Invalid configuration")
    
    processor = DataProcessor(config)
    await processor.run()

if __name__ == "__main__":
    asyncio.run(main())
''',
        "data_processor.py": '''
"""Data processing module."""
import json
from typing import Dict, List, Optional
from pathlib import Path

class DataProcessor:
    """Process data files according to configuration."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.results: List[Dict] = []
        self._cache: Dict = {}
    
    async def run(self):
        """Main processing loop."""
        input_dir = Path(self.config["input_dir"])
        for file_path in input_dir.glob("*.json"):
            await self.process_file(file_path)
    
    async def process_file(self, file_path: Path):
        """Process individual file."""
        if str(file_path) in self._cache:
            return self._cache[str(file_path)]
        
        with open(file_path) as f:
            data = json.load(f)
        
        processed = self.transform_data(data)
        self._cache[str(file_path)] = processed
        self.results.append(processed)
        
        return processed
    
    def transform_data(self, data: Dict) -> Dict:
        """Transform data according to rules."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = value.upper()
            elif isinstance(value, (int, float)):
                result[key] = value * 2
            else:
                result[key] = str(value)
        return result
''',
        "utils.py": '''
"""Utility functions."""
from typing import Dict, Any

def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration dictionary."""
    required_fields = ["input_dir", "output_dir", "batch_size"]
    
    for field in required_fields:
        if field not in config:
            return False
    
    if not isinstance(config["batch_size"], int) or config["batch_size"] <= 0:
        return False
    
    return True

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from file."""
    import json
    with open(config_path) as f:
        return json.load(f)
'''
    }
    
    # Write files
    for filename, content in files.items():
        (project_dir / filename).write_text(content)
    
    # 1. Parse all files
    parser = Parser.for_language("python")
    profiler = PerformanceProfiler(enabled=True)
    
    processor = BatchProcessor(
        parser=parser,
        batch_size=10,
        profiler=profiler,
        mode=ProcessingMode.THREADED
    )
    
    files_list = list(project_dir.glob("*.py"))
    batch_results = list(processor.process_files(files_list, include_metrics=True))
    
    # 2. Combine all ASTs
    all_nodes = []
    for batch in batch_results:
        for file_result in batch.files:
            if file_result.success and file_result.node:
                all_nodes.extend(from_tree(file_result.node).to_list())
    
    # 3. Graph analysis
    builder = GraphBuilder(from_tree(all_nodes[0]).union(
        *[from_tree(node) for node in all_nodes[1:10]]  # Sample for demo
    ))
    
    graph = builder.to_graph(
        directed=True,
        include_control_flow=True,
        include_data_flow=True
    )
    
    # 4. Pattern detection
    async_pattern = parser.parse("async def func(): pass")
    pattern_builder = GraphBuilder(from_tree(async_pattern))
    pattern_graph = pattern_builder.to_graph(directed=True)
    
    matcher = PatternMatcher(pattern_graph)
    matches = matcher.find_matches(graph, max_matches=5)
    
    # 5. Export comprehensive results
    analysis_results = {
        'project_metrics': {
            'total_files': len(files_list),
            'total_nodes': len(all_nodes),
            'async_patterns': len(matches)
        },
        'file_results': [
            {
                'file': str(fr.path.name),
                'success': fr.success,
                'metrics': fr.metrics
            }
            for batch in batch_results for fr in batch.files
        ],
        'performance': profiler.get_summary()
    }
    
    # Export to multiple formats
    output_dir = Path("analysis_output")
    output_dir.mkdir(exist_ok=True)
    
    # JSON export
    engine = ExportEngine(analysis_results)
    engine.export_to_file(
        output_dir / "complete_analysis.json",
        ExportOptions(output_format=OutputFormat.JSON, indent=2)
    )
    
    print(f"Analysis complete: {len(all_nodes)} nodes analyzed")
    print(f"Found {len(matches)} async function patterns")
    
    return analysis_results

# Example 2: Custom language extension
def custom_language_extension():
    """Extend Pydantree with custom language analysis."""
    
    from pydantree.languages.base import Language, LanguageAnalyzer, SemanticNode, SemanticRole
    from pydantree.languages.registry import LanguageConfig, get_global_registry
    
    class CustomPythonAnalyzer(LanguageAnalyzer):
        """Enhanced Python analyzer with custom metrics."""
        
        def analyze_semantics(self, node, scope_stack=None):
            # Call parent implementation
            semantic_node = super().analyze_semantics(node, scope_stack)
            
            # Add custom attributes
            semantic_node.attributes.update({
                'custom_complexity': self.calculate_custom_complexity(node),
                'dependency_count': self.count_dependencies(node),
                'documentation_score': self.score_documentation(node)
            })
            
            return semantic_node
        
        def calculate_custom_complexity(self, node):
            """Custom complexity calculation."""
            complexity_weights = {
                'if_statement': 2,
                'for_statement': 3,
                'while_statement': 3,
                'try_statement': 4,
                'async_function_definition': 2,
                'lambda': 1
            }
            
            total = 1  # Base complexity
            for desc in node.descendants():
                total += complexity_weights.get(desc.type_name, 0)
            
            return total
        
        def count_dependencies(self, node):
            """Count import dependencies."""
            imports = node.find_all_by_type({"import_statement", "import_from_statement"})
            return len(set(imp.text for imp in imports))
        
        def score_documentation(self, node):
            """Score documentation quality."""
            docstrings = node.find_all_by_type("string")
            functions = node.find_all_by_type("function_definition")
            classes = node.find_all_by_type("class_definition")
            
            documentable = len(functions) + len(classes)
            if documentable == 0:
                return 1.0
            
            # Simple heuristic: count docstrings vs functions/classes
            doc_score = min(len(docstrings) / documentable, 1.0)
            return round(doc_score, 2)
        
        def extract_definitions(self, root):
            """Extract definitions with custom analysis."""
            definitions = super().extract_definitions(root)
            
            # Enhance with custom metrics
            for defn in definitions:
                defn.attributes['custom_score'] = (
                    defn.attributes.get('custom_complexity', 0) * 0.3 +
                    defn.attributes.get('dependency_count', 0) * 0.2 +
                    defn.attributes.get('documentation_score', 0) * 0.5
                )
            
            return definitions
    
    # Demo usage
    parser = Parser.for_language("python")
    code = '''
"""High-quality module with good documentation."""

import json
import asyncio
from typing import List, Dict

async def process_data(data: List[Dict]) -> Dict:
    """Process data asynchronously with error handling."""
    results = []
    
    for item in data:
        try:
            if item.get('valid', True):
                processed = await transform_item(item)
                results.append(processed)
        except Exception as e:
            logging.error(f"Error processing {item}: {e}")
    
    return {'results': results, 'count': len(results)}

class DataValidator:
    """Validate data items according to schema."""
    
    def __init__(self, schema: Dict):
        self.schema = schema
    
    def validate(self, item: Dict) -> bool:
        """Validate single item."""
        for field, rules in self.schema.items():
            if field not in item:
                return False
            if not self._check_type(item[field], rules.get('type')):
                return False
        return True
    
    def _check_type(self, value, expected_type):
        """Check value type."""
        return isinstance(value, expected_type)
'''
    
    ast_root = parser.parse(code)
    
    # Use custom analyzer
    config = LanguageConfig(
        name="enhanced_python",
        display_name="Enhanced Python",
        extensions=[".py"],
        tree_sitter_name="python",
        package_name="tree-sitter-python"
    )
    
    analyzer = CustomPythonAnalyzer(config)
    semantic_root = analyzer.analyze_semantics(ast_root)
    
    print("Custom Analysis Results:")
    print(f"Custom complexity: {semantic_root.attributes.get('custom_complexity', 0)}")
    print(f"Dependencies: {semantic_root.attributes.get('dependency_count', 0)}")
    print(f"Documentation score: {semantic_root.attributes.get('documentation_score', 0)}")
    
    # Extract and analyze definitions
    definitions = analyzer.extract_definitions(ast_root)
    for defn in definitions:
        print(f"{defn.role.value} '{defn.name}': score {defn.attributes.get('custom_score', 0):.2f}")
    
    return analyzer, definitions

# Example 3: Performance optimization workflows
def performance_optimization():
    """Performance optimization and monitoring workflows."""
    
    import time
    
    # Create performance test dataset
    test_files = []
    test_dir = Path("performance_test")
    test_dir.mkdir(exist_ok=True)
    
    # Generate files of varying sizes
    sizes = [100, 500, 1000, 2000]  # Lines of code
    
    for i, size in enumerate(sizes):
        content_lines = [f"# Performance test file {i+1} - {size} lines"]
        
        for j in range(size):
            if j % 10 == 0:
                content_lines.append(f"def function_{j}(param_{j}):")
                content_lines.append(f"    '''Function {j} docstring.'''")
                content_lines.append(f"    result = param_{j} * {j}")
                content_lines.append(f"    return result")
            elif j % 7 == 0:
                content_lines.append(f"class Class_{j}:")
                content_lines.append(f"    def __init__(self):")
                content_lines.append(f"        self.value = {j}")
            else:
                content_lines.append(f"variable_{j} = {j}")
        
        file_path = test_dir / f"test_file_{size}lines.py"
        file_path.write_text('\n'.join(content_lines))
        test_files.append(file_path)
    
    # Performance comparison
    parser = Parser.for_language("python")
    modes = [ProcessingMode.SEQUENTIAL, ProcessingMode.THREADED, ProcessingMode.HYBRID]
    
    results = {}
    
    for mode in modes:
        profiler = PerformanceProfiler(enabled=True, track_memory=True)
        
        processor = BatchProcessor(
            parser=parser,
            batch_size=2,
            profiler=profiler,
            max_workers=4,
            mode=mode
        )
        
        start_time = time.time()
        batch_results = list(processor.process_files(test_files, include_metrics=True))
        total_time = time.time() - start_time
        
        # Collect performance metrics
        total_nodes = sum(
            len(from_tree(fr.node).to_list()) if fr.success and fr.node else 0
            for batch in batch_results for fr in batch.files
        )
        
        performance_summary = profiler.get_summary()
        
        results[mode.value] = {
            'total_time': total_time,
            'nodes_processed': total_nodes,
            'throughput': total_nodes / total_time if total_time > 0 else 0,
            'memory_peak': performance_summary.get('memory_stats', {}).get('peak_mb', 0),
            'operations': performance_summary.get('total_operations', 0)
        }
        
        print(f"{mode.value:12}: {total_time:.2f}s, {total_nodes:5d} nodes, "
              f"{results[mode.value]['throughput']:.0f} nodes/s")
    
    # Find optimal configuration
    best_mode = max(results.items(), key=lambda x: x[1]['throughput'])
    print(f"\nOptimal mode: {best_mode[0]} ({best_mode[1]['throughput']:.0f} nodes/s)")
    
    return results

# Example 4: Real-world integration example
def real_world_integration():
    """Real-world example: code quality dashboard."""
    
    import json
    from datetime import datetime
    
    # Simulate real project structure
    project_root = Path("real_project")
    project_root.mkdir(exist_ok=True)
    
    # Create realistic project files
    project_files = {
        "src/core/engine.py": '''
"""Core processing engine."""

import asyncio
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

@dataclass
class ProcessingConfig:
    """Configuration for processing engine."""
    max_workers: int = 4
    batch_size: int = 100
    timeout: float = 30.0
    retry_attempts: int = 3

class ProcessingEngine:
    """High-performance data processing engine."""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.executor = ThreadPoolExecutor(max_workers=config.max_workers)
        self.stats = {"processed": 0, "errors": 0}
    
    async def process_batch(self, items: List[Dict]) -> List[Dict]:
        """Process a batch of items."""
        results = []
        
        for item in items:
            try:
                result = await self._process_single_item(item)
                results.append(result)
                self.stats["processed"] += 1
            except Exception as e:
                logging.error(f"Processing failed for {item}: {e}")
                self.stats["errors"] += 1
        
        return results
    
    async def _process_single_item(self, item: Dict) -> Dict:
        """Process single item with validation."""
        if not self._validate_item(item):
            raise ValueError(f"Invalid item: {item}")
        
        # Simulate processing
        await asyncio.sleep(0.001)
        
        return {
            "id": item.get("id"),
            "processed_at": datetime.now().isoformat(),
            "result": item.get("value", 0) * 2
        }
    
    def _validate_item(self, item: Dict) -> bool:
        """Validate item structure."""
        required_fields = ["id", "value"]
        return all(field in item for field in required_fields)
''',
        
        "src/utils/helpers.py": '''
"""Utility helper functions."""

def calculate_metrics(data):
    if not data:
        return {}
    
    return {
        "count": len(data),
        "sum": sum(data),
        "average": sum(data) / len(data),
        "min": min(data),
        "max": max(data)
    }

def format_output(results, format_type="json"):
    if format_type == "json":
        import json
        return json.dumps(results, indent=2)
    elif format_type == "csv":
        # Simple CSV formatting
        if isinstance(results, list) and results:
            headers = results[0].keys()
            lines = [",".join(headers)]
            for row in results:
                lines.append(",".join(str(row.get(h, "")) for h in headers))
            return "\\n".join(lines)
    return str(results)
''',
        
        "tests/test_engine.py": '''
"""Tests for processing engine."""

import pytest
import asyncio
from src.core.engine import ProcessingEngine, ProcessingConfig

class TestProcessingEngine:
    
    @pytest.fixture
    def config(self):
        return ProcessingConfig(max_workers=2, batch_size=10)
    
    @pytest.fixture
    def engine(self, config):
        return ProcessingEngine(config)
    
    def test_config_creation(self, config):
        assert config.max_workers == 2
        assert config.batch_size == 10
    
    @pytest.mark.asyncio
    async def test_process_single_item(self, engine):
        item = {"id": "test1", "value": 42}
        result = await engine._process_single_item(item)
        
        assert result["id"] == "test1"
        assert result["result"] == 84
        assert "processed_at" in result
    
    @pytest.mark.asyncio
    async def test_process_batch(self, engine):
        items = [
            {"id": "test1", "value": 10},
            {"id": "test2", "value": 20}
        ]
        
        results = await engine.process_batch(items)
        assert len(results) == 2
        assert results[0]["result"] == 20
        assert results[1]["result"] == 40
'''
    }
    
    # Create directory structure and files
    for file_path, content in project_files.items():
        full_path = project_root / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
    
    # Comprehensive analysis pipeline
    parser = Parser.for_language("python")
    profiler = PerformanceProfiler(enabled=True)
    
    # 1. Batch process all Python files
    processor = BatchProcessor(
        parser=parser,
        batch_size=5,
        profiler=profiler,
        mode=ProcessingMode.THREADED
    )
    
    py_files = list(project_root.rglob("*.py"))
    batch_results = list(processor.process_files(py_files, include_metrics=True))
    
    # 2. Aggregate metrics
    dashboard_data = {
        "timestamp": datetime.now().isoformat(),
        "project_stats": {
            "total_files": len(py_files),
            "total_lines": 0,
            "total_functions": 0,
            "total_classes": 0,
            "avg_complexity": 0,
            "test_coverage": 0
        },
        "file_details": [],
        "quality_issues": [],
        "performance": profiler.get_summary()
    }
    
    complexities = []
    
    for batch in batch_results:
        for file_result in batch.files:
            if file_result.success and file_result.metrics:
                metrics = file_result.metrics
                
                # Aggregate stats
                dashboard_data["project_stats"]["total_lines"] += metrics.get("line_count", 0)
                dashboard_data["project_stats"]["total_functions"] += metrics.get("functions", 0)
                dashboard_data["project_stats"]["total_classes"] += metrics.get("classes", 0)
                
                complexity = metrics.get("cyclomatic_complexity", 0)
                complexities.append(complexity)
                
                # File details
                rel_path = file_result.path.relative_to(project_root)
                file_detail = {
                    "path": str(rel_path),
                    "lines": metrics.get("line_count", 0),
                    "functions": metrics.get("functions", 0),
                    "classes": metrics.get("classes", 0),
                    "complexity": complexity,
                    "is_test": "test" in str(rel_path)
                }
                dashboard_data["file_details"].append(file_detail)
                
                # Quality issues
                if complexity > 10:
                    dashboard_data["quality_issues"].append({
                        "file": str(rel_path),
                        "issue": "High complexity",
                        "value": complexity,
                        "severity": "warning" if complexity < 20 else "error"
                    })
    
    # Calculate averages
    if complexities:
        dashboard_data["project_stats"]["avg_complexity"] = sum(complexities) / len(complexities)
    
    # Test coverage estimation
    test_files = [f for f in dashboard_data["file_details"] if f["is_test"]]
    src_files = [f for f in dashboard_data["file_details"] if not f["is_test"]]
    
    if src_files:
        dashboard_data["project_stats"]["test_coverage"] = len(test_files) / len(src_files) * 100
    
    # 3. Export dashboard
    output_dir = Path("quality_dashboard")
    output_dir.mkdir(exist_ok=True)
    
    # JSON export for API consumption
    with open(output_dir / "dashboard_data.json", "w") as f:
        json.dump(dashboard_data, f, indent=2)
    
    # CSV export for spreadsheet analysis
    engine = ExportEngine(dashboard_data["file_details"])
    engine.export_to_file(
        output_dir / "file_metrics.csv",
        ExportOptions(output_format=OutputFormat.CSV)
    )
    
    print("Quality Dashboard Generated:")
    print(f"  Files analyzed: {dashboard_data['project_stats']['total_files']}")
    print(f"  Total lines: {dashboard_data['project_stats']['total_lines']:,}")
    print(f"  Average complexity: {dashboard_data['project_stats']['avg_complexity']:.1f}")
    print(f"  Quality issues: {len(dashboard_data['quality_issues'])}")
    print(f"  Test coverage: {dashboard_data['project_stats']['test_coverage']:.1f}%")
    
    return dashboard_data

if __name__ == "__main__":
    print("=== Advanced Integration Examples ===\n")
    
    print("1. Complete analysis pipeline:")
    code_analysis_pipeline()
    
    print("\n2. Custom language extension:")
    custom_language_extension()
    
    print("\n3. Performance optimization:")
    performance_optimization()
    
    print("\n4. Real-world integration:")
    real_world_integration()
