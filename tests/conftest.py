# tests/conftest.py
from __future__ import annotations

import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Generator
from unittest.mock import Mock, patch

from pydantree.core.container import Container, get_container
from pydantree.core.config import Config
from pydantree.core.profiler import PerformanceProfiler
from pydantree.core.parsers import Parser, MultiLanguageParser
from pydantree.processing.collections import NodeGroup
from pydantree.languages.registry import LanguageRegistry, LanguageConfig


@pytest.fixture(scope="session")
def sample_code_files() -> Dict[str, str]:
    """Sample code files for testing."""
    return {
        "python": '''
def hello_world(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}!"

class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b
        ''',
        "javascript": '''
function helloWorld(name) {
    return `Hello, ${name}!`;
}

class Calculator {
    add(a, b) {
        return a + b;
    }
}
        ''',
        "rust": '''
fn hello_world(name: &str) -> String {
    format!("Hello, {}!", name)
}

struct Calculator;

impl Calculator {
    fn add(&self, a: i32, b: i32) -> i32 {
        a + b
    }
}
        '''
    }


@pytest.fixture
def temp_files(sample_code_files) -> Generator[Dict[str, Path], None, None]:
    """Create temporary files with sample code."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        files = {}
        
        for lang, code in sample_code_files.items():
            ext_map = {"python": ".py", "javascript": ".js", "rust": ".rs"}
            file_path = temp_path / f"sample{ext_map.get(lang, '.txt')}"
            file_path.write_text(code)
            files[lang] = file_path
        
        yield files


@pytest.fixture
def clean_container():
    """Provide a clean container for each test."""
    container = Container()
    
    # Register test configurations
    test_config = Config(
        cache_enabled=False,
        profiling_enabled=False,
        debug_mode=True,
        strict_mode=False
    )
    container.register_singleton(Config, test_config)
    
    yield container
    container.clear()


@pytest.fixture
def mock_parser():
    """Mock parser for testing without tree-sitter dependencies."""
    parser = Mock(spec=Parser)
    parser.language_name = "python"
    parser.parse.return_value = Mock()  # Mock TSNode
    parser.parse_file.return_value = Mock()
    return parser


@pytest.fixture
def performance_profiler():
    """Performance profiler for testing."""
    return PerformanceProfiler(enabled=True, track_memory=False)


@pytest.fixture
def sample_nodegroup():
    """Sample NodeGroup for testing."""
    from pydantree.core.nodes import TSNode, TSPoint
    
    # Create mock nodes
    nodes = []
    for i in range(5):
        node = TSNode(
            type_name=f"node_{i}",
            start_byte=i * 10,
            end_byte=(i + 1) * 10,
            start_point=TSPoint(row=i, column=0),
            end_point=TSPoint(row=i, column=10),
            text=f"sample text {i}",
            children=[],
            is_named=True
        )
        nodes.append(node)
    
    return NodeGroup(nodes)


class TestHelper:
    """Test utilities and helpers."""
    
    @staticmethod
    def create_mock_node(type_name: str = "test_node", text: str = "test") -> Mock:
        """Create a mock TSNode."""
        node = Mock()
        node.type_name = type_name
        node.text = text
        node.start_byte = 0
        node.end_byte = len(text)
        node.children = []
        node.is_named = True
        node.structural_hash = "testhash"
        return node
    
    @staticmethod
    def assert_performance_within_limits(profiler: PerformanceProfiler, 
                                       operation: str, 
                                       max_time: float = 1.0):
        """Assert operation completed within time limits."""
        stats = profiler.get_summary()
        if operation in stats.get('top_operations', {}):
            op_time = stats['top_operations'][operation]['total_time']
            assert op_time < max_time, f"Operation {operation} took {op_time}s, exceeds {max_time}s"
    
    @staticmethod
    def create_test_config(**overrides) -> Config:
        """Create test configuration with overrides."""
        defaults = {
            "cache_enabled": False,
            "profiling_enabled": False,
            "debug_mode": True,
            "strict_mode": False
        }
        defaults.update(overrides)
        return Config(**defaults)


@pytest.fixture
def test_helper():
    """Test helper utilities."""
    return TestHelper


# Parametrized fixtures for different languages
@pytest.fixture(params=["python", "javascript", "rust"])
def language_code(request, sample_code_files):
    """Parametrized fixture for different language codes."""
    return request.param, sample_code_files[request.param]


# Performance testing fixtures
@pytest.fixture
def performance_baseline():
    """Baseline performance metrics for regression testing."""
    return {
        "parse_file": {"max_time": 0.1, "max_memory": 50},
        "batch_process": {"max_time": 5.0, "max_memory": 200},
        "export_json": {"max_time": 0.05, "max_memory": 25}
    }


# Integration test fixtures
@pytest.fixture
def integration_test_project(temp_files):
    """Create a test project structure for integration tests."""
    project_root = temp_files["python"].parent
    
    # Create additional files
    (project_root / "src").mkdir()
    (project_root / "src" / "__init__.py").write_text("")
    (project_root / "src" / "module.py").write_text("def test_function(): pass")
    
    (project_root / "tests").mkdir()
    (project_root / "tests" / "test_example.py").write_text("def test_example(): assert True")
    
    return project_root


# Property-based testing setup
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")
    config.addinivalue_line("markers", "property: marks tests as property-based tests")


# Skip markers for optional dependencies
def skip_if_no_tree_sitter():
    """Skip test if tree-sitter is not available."""
    try:
        import tree_sitter
        return pytest.mark.skipif(False, reason="")
    except ImportError:
        return pytest.mark.skipif(True, reason="tree-sitter not available")


def skip_if_no_optional_dep(package: str):
    """Skip test if optional dependency is not available."""
    try:
        __import__(package)
        return pytest.mark.skipif(False, reason="")
    except ImportError:
        return pytest.mark.skipif(True, reason=f"{package} not available")
