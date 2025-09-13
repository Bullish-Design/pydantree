# tests/test_core.py
from __future__ import annotations

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch

from pydantree.core.container import Container, inject
from pydantree.core.config import Config
from pydantree.core.profiler import PerformanceProfiler
from pydantree.core.errors import *
from pydantree.core.universal import UniversalGrammarSystem


class TestContainer:
    """Test dependency injection container."""
    
    def test_singleton_registration(self, clean_container):
        instance = Mock()
        clean_container.register_singleton(Mock, instance)
        assert clean_container.get(Mock) is instance
    
    def test_factory_registration(self, clean_container):
        factory = lambda: Mock()
        clean_container.register_factory(Mock, factory)
        result = clean_container.get(Mock)
        assert isinstance(result, Mock)
    
    def test_missing_service_raises_error(self, clean_container):
        with pytest.raises(ValueError, match="Service not registered"):
            clean_container.get(str)


class TestConfig:
    """Test configuration system."""
    
    def test_default_config_creation(self):
        config = Config()
        assert config.cache_enabled is True
        assert config.default_workers > 0
        assert config.batch_size == 100
    
    def test_config_with_overrides(self):
        config = Config(cache_enabled=False, batch_size=50)
        assert config.cache_enabled is False
        assert config.batch_size == 50
    
    @patch.dict('os.environ', {'PYDANTREE_CACHE_ENABLED': 'false'})
    def test_env_override(self):
        config = Config()
        assert config.cache_enabled is False


class TestPerformanceProfiler:
    """Test performance profiler."""
    
    def test_profiler_context_manager(self):
        profiler = PerformanceProfiler(enabled=True, track_memory=False)
        
        with profiler.profile("test_operation"):
            time.sleep(0.01)
        
        summary = profiler.get_summary()
        assert summary['total_operations'] == 1
        assert 'test_operation' in summary['top_operations']
    
    def test_profiler_disabled(self):
        profiler = PerformanceProfiler(enabled=False)
        
        with profiler.profile("test_operation"):
            time.sleep(0.01)
        
        summary = profiler.get_summary()
        assert summary['status'] == 'no_data'
    
    def test_nested_profiling(self):
        profiler = PerformanceProfiler(enabled=True, track_memory=False)
        
        with profiler.profile("outer"):
            with profiler.profile("inner"):
                time.sleep(0.01)
        
        summary = profiler.get_summary()
        assert summary['total_operations'] == 2
        assert 'outer' in summary['top_operations']
        assert 'inner' in summary['top_operations']


class TestErrorHandling:
    """Test error handling system."""
    
    def test_pydantree_error_with_context(self):
        error = PydantreeError("test error", {"file": "test.py"})
        assert error.message == "test error"
        assert error.context["file"] == "test.py"
    
    def test_retry_decorator_success(self):
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_attempts=3, base_delay=0.001))
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise IOError("temporary failure")
            return "success"
        
        result = flaky_function()
        assert result == "success"
        assert call_count == 2
    
    def test_retry_decorator_exhausted(self):
        @retry_with_backoff(RetryConfig(max_attempts=2, base_delay=0.001))
        def always_fails():
            raise IOError("permanent failure")
        
        with pytest.raises(IOError, match="permanent failure"):
            always_fails()
    
    def test_circuit_breaker_opens(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        def failing_func():
            raise Exception("failure")
        
        # First failure
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        # Second failure - circuit should open
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        # Circuit should now be open
        with pytest.raises(PydantreeError, match="Circuit breaker is OPEN"):
            cb.call(failing_func)
    
    def test_error_context_manager(self):
        with pytest.raises(PydantreeError) as exc_info:
            with ErrorContext("test_operation") as ctx:
                ctx.add_context("file", "test.py")
                raise ValueError("original error")
        
        assert "test_operation" in str(exc_info.value)
        assert exc_info.value.context["file"] == "test.py"


class TestUniversalGrammar:
    """Test universal grammar system."""
    
    def test_grammar_discovery(self):
        system = UniversalGrammarSystem()
        languages = system.get_available_languages()
        assert isinstance(languages, list)
        # Should at least have some languages available in testing
    
    def test_content_detection_python(self):
        system = UniversalGrammarSystem()
        python_code = "def hello():\n    print('world')"
        
        detected = system.detect_language_comprehensive(python_code)
        # Only test if python grammar is available
        if "python" in system.get_available_languages():
            assert detected == "python"
    
    def test_content_detection_json(self):
        system = UniversalGrammarSystem()
        json_code = '{"key": "value", "number": 42}'
        
        detected = system.detect_language_comprehensive(json_code)
        if "json" in system.get_available_languages():
            assert detected == "json"
    
    def test_universal_node_mapping(self):
        system = UniversalGrammarSystem()
        
        # Test function mapping
        universal = system.get_universal_mapping("function_definition", "python")
        assert universal == "function"
        
        # Test class mapping
        universal = system.get_universal_mapping("class_definition", "python")
        assert universal == "class"
    
    def test_language_support_analysis(self):
        system = UniversalGrammarSystem()
        analysis = system.analyze_language_support()
        
        assert "total_known" in analysis
        assert "available" in analysis
        assert "coverage_percent" in analysis
        assert isinstance(analysis["available_languages"], list)


@pytest.mark.integration
class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_container_with_config_injection(self, clean_container):
        # Register config
        config = Config(cache_enabled=True, batch_size=200)
        clean_container.register_singleton(Config, config)
        
        # Inject config
        #injected_config = inject(Config)
        from pydantree.core.container import inject_from
        injected_config = inject_from(clean_container, Config)

        assert injected_config.batch_size == 200
    
    def test_profiler_with_error_handling(self):
        profiler = PerformanceProfiler(enabled=True, track_memory=False)
        
        with pytest.raises(PydantreeError):
            with profiler.profile("error_operation"):
                with ErrorContext("test") as ctx:
                    ctx.add_context("operation", "error_operation")
                    raise ValueError("test error")
        
        summary = profiler.get_summary()
        assert "error_operation" in summary['top_operations']


@pytest.mark.performance
class TestPerformance:
    """Performance regression tests."""
    
    def test_config_creation_performance(self, performance_baseline):
        profiler = PerformanceProfiler(enabled=True, track_memory=False)
        
        with profiler.profile("config_creation"):
            for _ in range(100):
                Config()
        
        summary = profiler.get_summary()
        total_time = summary['top_operations']['config_creation']['total_time']
        assert total_time < 0.2  # Should create 100 configs in <200ms
    
    def test_container_injection_performance(self, clean_container):
        # Register service
        clean_container.register_singleton(str, "test_string")
        
        profiler = PerformanceProfiler(enabled=True, track_memory=False)
        
        with profiler.profile("injection"):
            for _ in range(1000):
                clean_container.get(str)
        
        summary = profiler.get_summary()
        total_time = summary['top_operations']['injection']['total_time']
        assert total_time < 0.1  # Should do 1000 injections in <100ms


@pytest.mark.property
class TestPropertyBased:
    """Property-based tests using hypothesis (if available)."""
    
    def test_config_invariants(self):
        """Test that config always maintains valid state."""
        config = Config()
        
        # Invariants that should always hold
        assert config.default_workers > 0
        assert config.batch_size > 0
        assert config.max_cache_size_mb > 0
        assert config.parser_pool_size > 0
    
    def test_error_context_preservation(self):
        """Test that error context is always preserved."""
        original_context = {"key": "value", "number": 42}
        
        error = PydantreeError("test", original_context)
        
        # Context should be preserved and not modified
        assert error.context == original_context
        assert error.context is not original_context  # Should be a copy
