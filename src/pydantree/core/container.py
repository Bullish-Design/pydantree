# pydantree/core/container.py
from __future__ import annotations

import threading
from typing import TypeVar, Type, Dict, Any, Optional, Callable, Protocol
from functools import lru_cache

T = TypeVar('T')


class Injectable(Protocol):
    """Protocol for injectable components."""
    pass


class Container:
    """Simple dependency injection container for development speed."""
    
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable[[], Any]] = {}
        self._singletons: Dict[Type, Any] = {}
        self._lock = threading.RLock()
    
    def register_singleton(self, interface: Type[T], instance: T) -> None:
        """Register a singleton instance."""
        with self._lock:
            self._singletons[interface] = instance
    
    def register_factory(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """Register a factory function."""
        with self._lock:
            self._factories[interface] = factory
    
    def register_transient(self, interface: Type[T], implementation: Type[T]) -> None:
        """Register a transient service (new instance each time)."""
        with self._lock:
            self._services[interface] = implementation
    
    def get(self, interface: Type[T]) -> T:
        """Get service instance."""
        with self._lock:
            # Check singletons first
            if interface in self._singletons:
                return self._singletons[interface]
            
            # Check factories
            if interface in self._factories:
                instance = self._factories[interface]()
                self._singletons[interface] = instance  # Cache factory results
                return instance
            
            # Check transient services
            if interface in self._services:
                return self._services[interface]()
            
            raise ValueError(f"Service not registered: {interface}")
    
    def clear(self) -> None:
        """Clear all registrations (useful for testing)."""
        with self._lock:
            self._services.clear()
            self._factories.clear()
            self._singletons.clear()


# Global container instance
_container: Optional[Container] = None
_container_lock = threading.Lock()


def get_container() -> Container:
    """Get global container instance."""
    global _container
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = Container()
                _setup_default_services(_container)
    return _container


def _setup_default_services(container: Container) -> None:
    """Setup default service registrations."""
    from .config import Config, get_default_config
    from .profiler import PerformanceProfiler
    
    container.register_factory(Config, get_default_config)
    container.register_factory(PerformanceProfiler, lambda: PerformanceProfiler(enabled=True))


def inject(interface: Type[T]) -> T:
    """Simple injection decorator/function."""
    return get_container().get(interface)

# Test-friendly injection that can use a specific container
def inject_from(container: Container, interface: Type[T]) -> T:
    """Inject from specific container (useful for testing)."""
    return container.get(interface)

