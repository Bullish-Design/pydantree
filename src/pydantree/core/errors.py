# pydantree/core/errors.py
from __future__ import annotations

import time
import logging
from typing import Any, Dict, Optional, Type, Callable, Union
from functools import wraps
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel


class PydantreeError(Exception):
    """Base exception for all Pydantree errors."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.context = (context or {}).copy()  # Copy to avoid reference sharing       #context or {}


class ParseError(PydantreeError):
    """Error during parsing operations."""
    
    def __init__(self, message: str, file_path: Optional[Path] = None, language: Optional[str] = None):
        super().__init__(message)
        self.file_path = file_path
        self.language = language


class LanguageNotSupportedError(PydantreeError):
    """Language is not supported or not available."""
    
    def __init__(self, language: str, available_languages: Optional[list] = None):
        super().__init__(f"Language '{language}' is not supported")
        self.language = language
        self.available_languages = available_languages or []


class ConfigurationError(PydantreeError):
    """Configuration-related errors."""
    pass


class CacheError(PydantreeError):
    """Cache-related errors."""
    pass


class ProcessingError(PydantreeError):
    """Batch processing errors."""
    
    def __init__(self, message: str, failed_files: Optional[list] = None):
        super().__init__(message)
        self.failed_files = failed_files or []


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    exponential_backoff: bool = True
    max_delay: float = 60.0
    retryable_exceptions: tuple = (IOError, OSError, ConnectionError)


class CircuitBreaker:
    """Circuit breaker pattern for preventing cascade failures."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise PydantreeError("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            
            raise


def retry_with_backoff(config: RetryConfig = None):
    """Decorator for retrying operations with exponential backoff."""
    if config is None:
        config = RetryConfig()
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = config.base_delay
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    if attempt == config.max_attempts - 1:
                        raise
                    
                    logging.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                    
                    if config.exponential_backoff:
                        delay = min(delay * 2, config.max_delay)
                except Exception:
                    # Non-retryable exception
                    raise
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


class GracefulDegradation:
    """Handles graceful degradation when optional features fail."""
    
    def __init__(self):
        self._fallbacks: Dict[str, Callable] = {}
        self._disabled_features: set = set()
    
    def register_fallback(self, feature: str, fallback: Callable):
        """Register a fallback function for a feature."""
        self._fallbacks[feature] = fallback
    
    def disable_feature(self, feature: str):
        """Permanently disable a feature."""
        self._disabled_features.add(feature)
    
    def try_with_fallback(self, feature: str, primary_func: Callable, *args, **kwargs):
        """Try primary function, fall back if it fails."""
        if feature in self._disabled_features:
            if feature in self._fallbacks:
                return self._fallbacks[feature](*args, **kwargs)
            return None
        
        try:
            return primary_func(*args, **kwargs)
        except Exception as e:
            logging.warning(f"Feature '{feature}' failed: {e}. Using fallback.")
            
            if feature in self._fallbacks:
                try:
                    return self._fallbacks[feature](*args, **kwargs)
                except Exception:
                    self.disable_feature(feature)
                    return None
            
            self.disable_feature(feature)
            return None


# Global instances
_graceful_degradation = GracefulDegradation()
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker()
    return _circuit_breakers[name]


def safe_operation(feature: str, fallback: Optional[Callable] = None):
    """Decorator for safe operations with graceful degradation."""
    def decorator(func):
        if fallback:
            _graceful_degradation.register_fallback(feature, fallback)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return _graceful_degradation.try_with_fallback(feature, func, *args, **kwargs)
        return wrapper
    return decorator


def handle_import_error(package: str, feature: str):
    """Handle missing optional dependencies gracefully."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ImportError:
                raise PydantreeError(
                    f"Feature '{feature}' requires {package}. Install with: pip install {package}"
                )
        return wrapper
    return decorator


class ErrorContext:
    """Context manager for collecting error information."""
    
    def __init__(self, operation: str):
        self.operation = operation
        self.context: Dict[str, Any] = {}
    
    def add_context(self, key: str, value: Any):
        """Add context information."""
        self.context[key] = value
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and issubclass(exc_type, PydantreeError):
            exc_val.context.update(self.context)
        elif exc_type:
            # Wrap non-Pydantree exceptions
            raise PydantreeError(
                f"Error in {self.operation}: {exc_val}",
                context=self.context
            ) from exc_val


def validate_file_path(file_path: Path) -> None:
    """Validate file path with helpful error messages."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")
    
    if file_path.stat().st_size == 0:
        raise ValueError(f"File is empty: {file_path}")


def validate_language_support(language: str, available_languages: list):
    """Validate language is supported."""
    if language not in available_languages:
        raise LanguageNotSupportedError(language, available_languages)


# Error recovery utilities
def recover_from_parse_error(error: ParseError, fallback_language: str = "text") -> Optional[str]:
    """Attempt to recover from parse errors."""
    if error.file_path and fallback_language:
        logging.info(f"Attempting recovery with fallback language: {fallback_language}")
        return fallback_language
    return None


def create_error_report(error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create structured error report."""
    return {
        "error_type": type(error).__name__,
        "message": str(error),
        "context": getattr(error, "context", context or {}),
        "timestamp": time.time(),
        "recoverable": isinstance(error, (ParseError, LanguageNotSupportedError))
    }
