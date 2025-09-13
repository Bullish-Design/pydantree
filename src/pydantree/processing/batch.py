# pydantree/processing/batch.py
from __future__ import annotations

import time
import asyncio
import threading
from pathlib import Path
from typing import List, Iterator, Optional, Dict, Any, Union, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from queue import Queue, Empty, PriorityQueue
import itertools
from enum import Enum

from pydantic import BaseModel, TypeAdapter, Field

from ..core.parsers import Parser, MultiLanguageParser#, LanguageRegistry
from ..core.nodes import TSNode
from ..core.profiler import PerformanceProfiler


class ProcessingPriority(Enum):
    """Processing priority levels."""
    LOW = 3
    NORMAL = 2  
    HIGH = 1
    CRITICAL = 0


class ProcessingMode(Enum):
    """Batch processing execution modes."""
    SEQUENTIAL = "sequential"
    THREADED = "threaded"
    PROCESS = "process"
    ASYNC = "async"
    HYBRID = "hybrid"


def batched(iterable, n):
    """Batch iterable into chunks of size n (Python 3.12+ compatibility)."""
    iterator = iter(iterable)
    while chunk := list(itertools.islice(iterator, n)):
        yield chunk


@dataclass
class FileResult:
    """Enhanced result of processing a single file."""
    path: Path
    language: Optional[str] = None
    node: Optional[TSNode] = None
    error: Optional[str] = None
    parse_time: float = 0.0
    file_size: int = 0
    metrics: Optional[Dict[str, Any]] = None
    priority: ProcessingPriority = ProcessingPriority.NORMAL
    
    @property
    def success(self) -> bool:
        return self.error is None
    
    @property
    def processing_rate(self) -> float:
        """Processing rate in bytes per second."""
        if self.parse_time > 0 and self.file_size > 0:
            return self.file_size / self.parse_time
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dictionary."""
        result = {
            'path': str(self.path),
            'language': self.language,
            'success': self.success,
            'parse_time': self.parse_time,
            'file_size': self.file_size,
            'processing_rate': self.processing_rate,
            'priority': self.priority.name
        }
        
        if self.error:
            result['error'] = self.error
        if self.metrics:
            result['metrics'] = self.metrics
        if self.node and not self.error:
            result['node_type'] = self.node.type_name
            result['node_count'] = self.node.descendants_count
            result['complexity'] = self.node.calculate_complexity()
        
        return result


@dataclass
class BatchResult:
    """Enhanced result of processing a batch of files."""
    files: List[FileResult]
    batch_time: float
    batch_size: int
    batch_id: Optional[str] = None
    mode: ProcessingMode = ProcessingMode.SEQUENTIAL
    worker_count: int = 1
    
    @property
    def success_count(self) -> int:
        return len([f for f in self.files if f.success])
    
    @property
    def error_count(self) -> int:
        return len([f for f in self.files if not f.success])
    
    @property
    def success_rate(self) -> float:
        if not self.files:
            return 0.0
        return self.success_count / len(self.files)
    
    @property
    def total_bytes(self) -> int:
        return sum(f.file_size for f in self.files)
    
    @property
    def throughput(self) -> float:
        """Throughput in bytes per second."""
        if self.batch_time > 0 and self.total_bytes > 0:
            return self.total_bytes / self.batch_time
        return 0.0
    
    def get_language_distribution(self) -> Dict[str, int]:
        """Get distribution of languages in this batch."""
        distribution = {}
        for file_result in self.files:
            if file_result.language:
                distribution[file_result.language] = distribution.get(file_result.language, 0) + 1
        return distribution
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get detailed performance statistics."""
        successful_files = [f for f in self.files if f.success]
        
        if not successful_files:
            return {'error': 'No successful files to analyze'}
        
        parse_times = [f.parse_time for f in successful_files]
        file_sizes = [f.file_size for f in successful_files]
        
        return {
            'avg_parse_time': sum(parse_times) / len(parse_times),
            'min_parse_time': min(parse_times),
            'max_parse_time': max(parse_times),
            'avg_file_size': sum(file_sizes) / len(file_sizes),
            'total_bytes_processed': sum(file_sizes),
            'throughput_bps': self.throughput,
            'files_per_second': len(successful_files) / self.batch_time if self.batch_time > 0 else 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dictionary."""
        return {
            'batch_id': self.batch_id,
            'mode': self.mode.value,
            'worker_count': self.worker_count,
            'files': [f.to_dict() for f in self.files],
            'summary': {
                'total_files': len(self.files),
                'successful': self.success_count,
                'failed': self.error_count,
                'success_rate': self.success_rate,
                'batch_time': self.batch_time,
                'throughput': self.throughput,
                'language_distribution': self.get_language_distribution()
            },
            'performance': self.get_performance_stats()
        }


class TypeAdapterCache:
    """High-performance TypeAdapter cache with LRU eviction."""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._cache: Dict[str, TypeAdapter] = {}
        self._access_order: List[str] = []
        self._lock = threading.RLock()
    
    def get_adapter(self, type_key: str, node_types: List[type]) -> TypeAdapter:
        """Get or create TypeAdapter for node types."""
        with self._lock:
            if type_key in self._cache:
                # Update access order
                self._access_order.remove(type_key)
                self._access_order.append(type_key)
                return self._cache[type_key]
            
            # Create new adapter
            if len(node_types) == 1:
                adapter = TypeAdapter(node_types[0])
            else:
                from typing import Union
                union_type = Union[tuple(node_types)]
                adapter = TypeAdapter(union_type)
            
            # Add to cache with LRU eviction
            if len(self._cache) >= self.max_size:
                # Remove least recently used
                lru_key = self._access_order.pop(0)
                del self._cache[lru_key]
            
            self._cache[type_key] = adapter
            self._access_order.append(type_key)
            return adapter
    
    def clear(self):
        """Clear the cache."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()


class BatchProcessor:
    """High-performance batch processor with advanced optimizations."""
    
    def __init__(self,
                 parser: Union[Parser, MultiLanguageParser],
                 batch_size: int = 100,
                 profiler: Optional[PerformanceProfiler] = None,
                 max_workers: Optional[int] = None,
                 mode: ProcessingMode = ProcessingMode.THREADED,
                 priority_queue_enabled: bool = False):
        """Initialize batch processor with advanced options."""
        self.parser = parser
        self.batch_size = batch_size
        self.profiler = profiler or PerformanceProfiler(enabled=False)
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.mode = mode
        self.priority_queue_enabled = priority_queue_enabled
        
        # Performance optimizations
        self._type_adapter_cache = TypeAdapterCache()
        self._statistics = {
            'total_files_processed': 0,
            'total_bytes_processed': 0,
            'total_processing_time': 0.0,
            'average_throughput': 0.0
        }
        
        # Priority queue for file processing
        self._file_queue: Optional[PriorityQueue] = PriorityQueue() if priority_queue_enabled else None
    
    def process_files(self,
                     files: List[Path],
                     include_metrics: bool = True,
                     progress_callback: Optional[Callable[[int, int], None]] = None) -> Iterator[BatchResult]:
        """Process files with configurable execution mode."""
        total_start = time.time()
        batch_counter = 0
        processed_count = 0
        
        with self.profiler.profile('batch_processing_setup'):
            file_batches = list(batched(files, self.batch_size))
        
        for batch_files in file_batches:
            batch_id = f"batch_{batch_counter:04d}"
            batch_counter += 1
            
            # Process batch based on mode
            if self.mode == ProcessingMode.PROCESS:
                result = self._process_batch_multiprocess(batch_files, include_metrics, batch_id)
            elif self.mode == ProcessingMode.ASYNC:
                result = asyncio.run(self._process_batch_async(batch_files, include_metrics, batch_id))
            elif self.mode == ProcessingMode.HYBRID:
                result = self._process_batch_hybrid(batch_files, include_metrics, batch_id)
            else:  # THREADED or SEQUENTIAL
                parallel = self.mode == ProcessingMode.THREADED
                result = self._process_batch_threaded(batch_files, include_metrics, batch_id, parallel)
            
            processed_count += len(batch_files)
            if progress_callback:
                progress_callback(processed_count, len(files))
            
            yield result
        
        # Update global statistics
        total_time = time.time() - total_start
        self._statistics['total_processing_time'] += total_time
        self._statistics['total_files_processed'] += len(files)
    
    def _process_batch_threaded(self,
                              files: List[Path],
                              include_metrics: bool,
                              batch_id: str,
                              parallel: bool = True) -> BatchResult:
        """Process batch with thread pool."""
        batch_start = time.time()
        
        if parallel and len(files) > 1:
            with self.profiler.profile(f'batch_threaded_{batch_id}'):
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {
                        executor.submit(self._process_single_file, file_path, include_metrics): file_path
                        for file_path in files
                    }
                    
                    results = []
                    for future in as_completed(futures):
                        try:
                            result = future.result(timeout=60)
                            results.append(result)
                        except Exception as e:
                            file_path = futures[future]
                            error_result = FileResult(
                                path=file_path,
                                error=f"Processing error: {e}",
                                parse_time=0.0
                            )
                            results.append(error_result)
        else:
            # Sequential processing
            with self.profiler.profile(f'batch_sequential_{batch_id}'):
                results = [self._process_single_file(f, include_metrics) for f in files]
        
        batch_time = time.time() - batch_start
        return BatchResult(
            files=results,
            batch_time=batch_time,
            batch_size=len(files),
            batch_id=batch_id,
            mode=self.mode,
            worker_count=self.max_workers if parallel else 1
        )
    
    def _process_batch_multiprocess(self,
                                   files: List[Path],
                                   include_metrics: bool,
                                   batch_id: str) -> BatchResult:
        """Process batch with process pool for CPU-intensive tasks."""
        batch_start = time.time()
        
        with self.profiler.profile(f'batch_process_{batch_id}'):
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(_process_file_worker, file_path, self.parser.language_name, include_metrics): file_path
                    for file_path in files
                }
                
                results = []
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=120)
                        results.append(result)
                    except Exception as e:
                        file_path = futures[future]
                        error_result = FileResult(
                            path=file_path,
                            error=f"Process error: {e}",
                            parse_time=0.0
                        )
                        results.append(error_result)
        
        batch_time = time.time() - batch_start
        return BatchResult(
            files=results,
            batch_time=batch_time,
            batch_size=len(files),
            batch_id=batch_id,
            mode=ProcessingMode.PROCESS,
            worker_count=self.max_workers
        )
    
    async def _process_batch_async(self,
                                  files: List[Path],
                                  include_metrics: bool,
                                  batch_id: str) -> BatchResult:
        """Process batch asynchronously with controlled concurrency."""
        batch_start = time.time()
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def process_file_async(file_path: Path) -> FileResult:
            async with semaphore:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    self._process_single_file,
                    file_path,
                    include_metrics
                )
        
        with self.profiler.profile(f'batch_async_{batch_id}'):
            tasks = [process_file_async(file_path) for file_path in files]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        file_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                file_results.append(FileResult(
                    path=files[i],
                    error=str(result),
                    parse_time=0.0
                ))
            else:
                file_results.append(result)
        
        batch_time = time.time() - batch_start
        return BatchResult(
            files=file_results,
            batch_time=batch_time,
            batch_size=len(files),
            batch_id=batch_id,
            mode=ProcessingMode.ASYNC,
            worker_count=self.max_workers
        )
    
    def _process_batch_hybrid(self,
                             files: List[Path],
                             include_metrics: bool,
                             batch_id: str) -> BatchResult:
        """Hybrid processing: small files in threads, large files in processes."""
        batch_start = time.time()
        
        # Separate files by size (threshold: 100KB)
        size_threshold = 100 * 1024
        small_files = []
        large_files = []
        
        for file_path in files:
            try:
                file_size = file_path.stat().st_size
                if file_size > size_threshold:
                    large_files.append(file_path)
                else:
                    small_files.append(file_path)
            except OSError:
                small_files.append(file_path)  # Default to small if can't stat
        
        results = []
        
        with self.profiler.profile(f'batch_hybrid_{batch_id}'):
            # Process small files with threads
            if small_files:
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    small_futures = {
                        executor.submit(self._process_single_file, f, include_metrics): f
                        for f in small_files
                    }
                    for future in as_completed(small_futures):
                        try:
                            results.append(future.result())
                        except Exception as e:
                            file_path = small_futures[future]
                            results.append(FileResult(
                                path=file_path,
                                error=f"Thread error: {e}",
                                parse_time=0.0
                            ))
            
            # Process large files with processes
            if large_files:
                with ProcessPoolExecutor(max_workers=max(2, self.max_workers // 2)) as executor:
                    large_futures = {
                        executor.submit(_process_file_worker, f, self.parser.language_name, include_metrics): f
                        for f in large_files
                    }
                    for future in as_completed(large_futures):
                        try:
                            results.append(future.result())
                        except Exception as e:
                            file_path = large_futures[future]
                            results.append(FileResult(
                                path=file_path,
                                error=f"Process error: {e}",
                                parse_time=0.0
                            ))
        
        batch_time = time.time() - batch_start
        return BatchResult(
            files=results,
            batch_time=batch_time,
            batch_size=len(files),
            batch_id=batch_id,
            mode=ProcessingMode.HYBRID,
            worker_count=self.max_workers
        )
    
    def _process_single_file(self,
                           file_path: Path,
                           include_metrics: bool) -> FileResult:
        """Process individual file with comprehensive error handling."""
        start_time = time.time()
        file_size = 0
        
        try:
            # Get file size
            file_size = file_path.stat().st_size
            
            with self.profiler.profile('read_file'):
                content = file_path.read_text(encoding='utf-8')
            
            # Determine language and parse
            language = None
            if isinstance(self.parser, MultiLanguageParser):
                language = LanguageRegistry.detect_language(file_path)
                if not language:
                    # Try content-based detection
                    language = LanguageRegistry.detect_from_content(content, file_path)
                
                if not language:
                    raise ValueError(f"Could not detect language for {file_path}")
                
                with self.profiler.profile(f'parse_{language}'):
                    node = self.parser.parse_with_language(content, language)
            else:
                language = self.parser.language_name
                with self.profiler.profile(f'parse_{language}'):
                    node = self.parser.parse(content)
            
            # Extract metrics if requested
            metrics = None
            if include_metrics:
                with self.profiler.profile('extract_metrics'):
                    metrics = node.get_metrics(include_advanced=True)
            
            parse_time = time.time() - start_time
            return FileResult(
                path=file_path,
                language=language,
                node=node,
                parse_time=parse_time,
                file_size=file_size,
                metrics=metrics
            )
            
        except Exception as e:
            parse_time = time.time() - start_time
            return FileResult(
                path=file_path,
                language=language,
                error=str(e),
                parse_time=parse_time,
                file_size=file_size
            )
    
    def process_directory(self,
                         directory: Path,
                         pattern: str = "*",
                         recursive: bool = True,
                         include_metrics: bool = True,
                         exclude_patterns: Optional[List[str]] = None,
                         priority_func: Optional[Callable[[Path], ProcessingPriority]] = None) -> Iterator[BatchResult]:
        """Process directory with advanced filtering and prioritization."""
        
        # Discover files
        files = self._discover_files(directory, pattern, recursive, exclude_patterns)
        
        if not files:
            return
        
        # Apply prioritization if enabled
        if priority_func and self.priority_queue_enabled:
            prioritized_files = [(priority_func(f).value, f) for f in files]
            prioritized_files.sort()
            files = [f for _, f in prioritized_files]
        
        # Process in batches
        yield from self.process_files(files, include_metrics)
    
    def _discover_files(self,
                       directory: Path,
                       pattern: str,
                       recursive: bool,
                       exclude_patterns: Optional[List[str]] = None) -> List[Path]:
        """Enhanced file discovery with exclusion patterns."""
        exclude_patterns = exclude_patterns or []
        files = []
        
        if isinstance(self.parser, MultiLanguageParser):
            # Multi-language file discovery
            extensions = self.parser.get_supported_extensions()
            for ext in extensions:
                pattern_with_ext = f"*{ext}"
                if recursive:
                    found_files = directory.rglob(pattern_with_ext)
                else:
                    found_files = directory.glob(pattern_with_ext)
                files.extend(found_files)
        else:
            # Single language discovery
            if recursive:
                files.extend(directory.rglob(pattern))
            else:
                files.extend(directory.glob(pattern))
        
        # Apply exclusion patterns
        if exclude_patterns:
            filtered_files = []
            for file_path in files:
                if not any(pattern in str(file_path) for pattern in exclude_patterns):
                    filtered_files.append(file_path)
            files = filtered_files
        
        return list(set(files))  # Remove duplicates
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics."""
        stats = self._statistics.copy()
        
        if stats['total_processing_time'] > 0:
            stats['average_throughput'] = stats['total_bytes_processed'] / stats['total_processing_time']
            stats['files_per_second'] = stats['total_files_processed'] / stats['total_processing_time']
        
        if self.profiler.enabled:
            stats['profiler_report'] = self.profiler.get_detailed_report()
        
        stats['cache_stats'] = {
            'type_adapter_cache_size': len(self._type_adapter_cache._cache),
            'parser_cache_stats': self.parser.get_cache_stats() if hasattr(self.parser, 'get_cache_stats') else None
        }
        
        return stats
    
    def clear_caches(self) -> None:
        """Clear all internal caches."""
        self._type_adapter_cache.clear()
        if hasattr(self.parser, 'clear_cache'):
            self.parser.clear_cache()
        elif hasattr(self.parser, 'clear_caches'):
            self.parser.clear_caches()


# Worker function for multiprocessing
def _process_file_worker(file_path: Path, language_name: str, include_metrics: bool) -> FileResult:
    """Worker function for process-based parallel processing."""
    from ..core.parsers import Parser
    
    start_time = time.time()
    
    try:
        # Create parser in worker process
        parser = Parser.for_language(language_name, use_pool=False)
        
        file_size = file_path.stat().st_size
        content = file_path.read_text(encoding='utf-8')
        
        node = parser.parse(content)
        
        metrics = None
        if include_metrics:
            metrics = node.get_metrics(include_advanced=True)
        
        parse_time = time.time() - start_time
        return FileResult(
            path=file_path,
            language=language_name,
            node=node,
            parse_time=parse_time,
            file_size=file_size,
            metrics=metrics
        )
    
    except Exception as e:
        parse_time = time.time() - start_time
        return FileResult(
            path=file_path,
            language=language_name,
            error=str(e),
            parse_time=parse_time,
            file_size=0
        )


# Utility functions
def discover_source_files(directory: Path,
                         languages: Optional[List[str]] = None,
                         include_hidden: bool = False,
                         max_size_mb: Optional[int] = None) -> List[Path]:
    """Enhanced source file discovery."""
    files = []
    
    if languages:
        for language in languages:
            config = LanguageRegistry.get_language_config(language)
            if config:
                for ext in config.extensions:
                    files.extend(directory.rglob(f"*{ext}"))
    else:
        # All supported languages
        for lang_name in LanguageRegistry.get_supported_languages():
            config = LanguageRegistry.get_language_config(lang_name)
            if config:
                for ext in config.extensions:
                    files.extend(directory.rglob(f"*{ext}"))
    
    # Apply filters
    filtered_files = []
    for file_path in files:
        # Skip hidden files
        if not include_hidden and any(part.startswith('.') for part in file_path.parts):
            continue
        
        # Size filter
        if max_size_mb:
            try:
                size_mb = file_path.stat().st_size / (1024 * 1024)
                if size_mb > max_size_mb:
                    continue
            except OSError:
                continue
        
        filtered_files.append(file_path)
    
    return list(set(filtered_files))


@contextmanager
def batch_processing_session(parser: Union[Parser, MultiLanguageParser],
                           batch_size: int = 100,
                           mode: ProcessingMode = ProcessingMode.THREADED,
                           enable_profiling: bool = True):
    """Context manager for batch processing with automatic resource management."""
    profiler = PerformanceProfiler(enabled=enable_profiling) if enable_profiling else None
    processor = BatchProcessor(parser, batch_size, profiler, mode=mode)
    
    try:
        yield processor
    finally:
        if profiler and enable_profiling:
            stats = processor.get_statistics()
            print(f"Batch processing complete:")
            print(f"  Files processed: {stats['total_files_processed']}")
            print(f"  Total time: {stats['total_processing_time']:.2f}s")
            print(f"  Average throughput: {stats.get('average_throughput', 0):.0f} bytes/s")


# Re-export for convenience
import os
