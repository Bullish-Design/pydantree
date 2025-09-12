# pydantree/export/engine.py
from __future__ import annotations

import json
import gzip
import lz4.frame
import zstandard as zstd
from pathlib import Path
from typing import Union, Dict, Any, List, Optional, Iterator, TextIO, BinaryIO
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from contextlib import contextmanager
import time
import threading
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, ConfigDict, Field

from ..core.nodes import TSNode
from ..core.profiler import PerformanceProfiler
from ..processing.batch import BatchResult, FileResult
from ..processing.collections import NodeGroup


class ExportFormat(Enum):
    """Supported export format types."""
    FULL = "full"
    CLEAN = "clean" 
    MINIMAL = "minimal"
    METRICS = "metrics"
    STRUCTURE = "structure"
    SUMMARY = "summary"


class OutputFormat(Enum):
    """Supported output formats."""
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    JSONL = "jsonl"
    PARQUET = "parquet"
    BINARY = "binary"
    DOT = "dot"
    GRAPHML = "graphml"


class CompressionType(Enum):
    """Supported compression types."""
    NONE = "none"
    GZIP = "gzip"
    LZ4 = "lz4"
    ZSTD = "zstd"


@dataclass
class ExportOptions:
    """Configuration options for export operations."""
    format: ExportFormat = ExportFormat.FULL
    output_format: OutputFormat = OutputFormat.JSON
    compression: CompressionType = CompressionType.NONE
    include_spans: bool = True
    include_children: bool = True
    include_computed: bool = False
    streaming: bool = False
    chunk_size: int = 1000
    indent: Optional[int] = 2
    workers: int = 1
    max_memory_mb: int = 1024
    

class ExportHandler(ABC):
    """Abstract base for format-specific export handlers."""
    
    @abstractmethod
    def export_node(self, node: TSNode, options: ExportOptions) -> Any:
        """Export a single node."""
        pass
    
    @abstractmethod
    def export_collection(self, items: Iterator[Any], output: TextIO, options: ExportOptions) -> Dict[str, Any]:
        """Export a collection of items to stream."""
        pass
    
    @abstractmethod
    def get_file_extension(self) -> str:
        """Get appropriate file extension for this handler."""
        pass


class JsonHandler(ExportHandler):
    """JSON export handler with optimization."""
    
    def export_node(self, node: TSNode, options: ExportOptions) -> Dict[str, Any]:
        """Export node as JSON-serializable dict."""
        return node.export_dict(
            mode=options.format.value,
            include_spans=options.include_spans,
            include_children=options.include_children,
            include_computed=options.include_computed
        )
    
    def export_collection(self, items: Iterator[Any], output: TextIO, options: ExportOptions) -> Dict[str, Any]:
        """Export collection as JSON array."""
        stats = {'items_exported': 0, 'bytes_written': 0}
        
        output.write('[')
        first_item = True
        
        for item in items:
            if not first_item:
                output.write(',')
            
            if options.streaming and options.indent:
                output.write('\n' + ' ' * options.indent)
            
            json_str = json.dumps(item, indent=None, separators=(',', ':'))
            output.write(json_str)
            
            stats['items_exported'] += 1
            stats['bytes_written'] += len(json_str.encode())
            first_item = False
        
        output.write(']')
        return stats
    
    def get_file_extension(self) -> str:
        return '.json'


class JsonlHandler(ExportHandler):
    """JSON Lines handler for streaming."""
    
    def export_node(self, node: TSNode, options: ExportOptions) -> Dict[str, Any]:
        return JsonHandler().export_node(node, options)
    
    def export_collection(self, items: Iterator[Any], output: TextIO, options: ExportOptions) -> Dict[str, Any]:
        """Export as JSON Lines (one JSON object per line)."""
        stats = {'items_exported': 0, 'bytes_written': 0}
        
        for item in items:
            json_str = json.dumps(item, separators=(',', ':'))
            output.write(json_str + '\n')
            
            stats['items_exported'] += 1
            stats['bytes_written'] += len(json_str.encode())
        
        return stats
    
    def get_file_extension(self) -> str:
        return '.jsonl'


class CsvHandler(ExportHandler):
    """CSV export handler."""
    
    def export_node(self, node: TSNode, options: ExportOptions) -> Dict[str, Any]:
        """Export node metrics as flat dict for CSV."""
        metrics = node.get_metrics(include_advanced=True)
        
        # Flatten nested dicts
        flattened = {}
        for key, value in metrics.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    flattened[f"{key}_{sub_key}"] = sub_value
            else:
                flattened[key] = value
        
        # Add core fields
        flattened.update({
            'type_name': node.type_name,
            'byte_length': node.byte_length,
            'line_count': node.line_count,
            'text_preview': node.text[:50].replace('\n', ' ').replace('\r', ''),
        })
        
        return flattened
    
    def export_collection(self, items: Iterator[Any], output: TextIO, options: ExportOptions) -> Dict[str, Any]:
        """Export as CSV with dynamic column detection."""
        import csv
        
        stats = {'items_exported': 0, 'bytes_written': 0}
        
        # Buffer first batch to determine columns
        item_buffer = []
        all_columns = set()
        
        # Collect first chunk to determine schema
        for i, item in enumerate(items):
            if i >= options.chunk_size:
                break
            item_buffer.append(item)
            if isinstance(item, dict):
                all_columns.update(item.keys())
        
        # Sort columns for consistent output
        columns = sorted(all_columns)
        
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        
        # Write buffered items
        for item in item_buffer:
            writer.writerow(item)
            stats['items_exported'] += 1
        
        # Continue with remaining items
        for item in items:
            writer.writerow(item)
            stats['items_exported'] += 1
        
        return stats
    
    def get_file_extension(self) -> str:
        return '.csv'


class BinaryHandler(ExportHandler):
    """High-performance binary export using msgpack."""
    
    def __init__(self):
        try:
            import msgpack
            self.msgpack = msgpack
        except ImportError:
            raise ImportError("msgpack required for binary export: pip install msgpack")
    
    def export_node(self, node: TSNode, options: ExportOptions) -> bytes:
        """Export node as binary msgpack."""
        data = JsonHandler().export_node(node, options)
        return self.msgpack.packb(data, use_bin_type=True)
    
    def export_collection(self, items: Iterator[Any], output: BinaryIO, options: ExportOptions) -> Dict[str, Any]:
        """Export collection as binary stream."""
        stats = {'items_exported': 0, 'bytes_written': 0}
        
        for item in items:
            packed = self.msgpack.packb(item, use_bin_type=True)
            # Write length prefix for streaming
            length = len(packed)
            output.write(length.to_bytes(4, byteorder='little'))
            output.write(packed)
            
            stats['items_exported'] += 1
            stats['bytes_written'] += 4 + length
        
        return stats
    
    def get_file_extension(self) -> str:
        return '.msgpack'


class ExportEngine:
    """Unified export engine with streaming and compression support."""
    
    def __init__(self, source: Union[TSNode, NodeGroup, BatchResult, List[TSNode]],
                 profiler: Optional[PerformanceProfiler] = None):
        """Initialize export engine with source object."""
        self.source = source
        self.source_type = type(source)
        self.profiler = profiler or PerformanceProfiler(enabled=False)
        
        # Initialize handlers
        self.handlers = {
            OutputFormat.JSON: JsonHandler(),
            OutputFormat.JSONL: JsonlHandler(),
            OutputFormat.CSV: CsvHandler(),
            OutputFormat.BINARY: BinaryHandler(),
        }
        
        self._stats = {
            'items_processed': 0,
            'bytes_written': 0,
            'compression_ratio': 1.0,
            'processing_time': 0.0
        }
    
    def export_to_file(self, output_path: Path, options: ExportOptions = None) -> Dict[str, Any]:
        """Export to file with optional compression and streaming."""
        options = options or ExportOptions()
        
        with self.profiler.profile('export_to_file'):
            start_time = time.time()
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get handler
            handler = self.handlers.get(options.output_format)
            if not handler:
                raise ValueError(f"Unsupported output format: {options.output_format}")
            
            # Determine file extension
            if output_path.suffix == '':
                output_path = output_path.with_suffix(handler.get_file_extension())
            
            # Export with compression
            if options.compression == CompressionType.NONE:
                stats = self._export_uncompressed(output_path, handler, options)
            else:
                stats = self._export_compressed(output_path, handler, options)
            
            # Update statistics
            processing_time = time.time() - start_time
            stats.update({
                'processing_time': processing_time,
                'output_path': str(output_path),
                'source_type': self.source_type.__name__,
                'options': options.__dict__
            })
            
            self._stats.update(stats)
            return stats
    
    def export_to_string(self, options: ExportOptions = None) -> str:
        """Export to string (memory-based)."""
        options = options or ExportOptions()
        
        if options.output_format == OutputFormat.BINARY:
            raise ValueError("Binary format not supported for string export")
        
        from io import StringIO
        buffer = StringIO()
        
        handler = self.handlers[options.output_format]
        items = self._get_export_items(options)
        
        with self.profiler.profile('export_to_string'):
            handler.export_collection(items, buffer, options)
        
        return buffer.getvalue()
    
    def stream_export(self, output_path: Path, options: ExportOptions = None) -> Iterator[Dict[str, Any]]:
        """Stream export with real-time progress reporting."""
        options = options or ExportOptions(streaming=True)
        
        # Create output file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        handler = self.handlers[options.output_format]
        items = self._get_export_items(options)
        
        # Stream with progress reporting
        processed = 0
        with self._open_output_file(output_path, options) as output:
            for chunk in self._chunk_items(items, options.chunk_size):
                chunk_stats = handler.export_collection(iter(chunk), output, options)
                processed += len(chunk)
                
                yield {
                    'chunk_processed': len(chunk),
                    'total_processed': processed,
                    'chunk_stats': chunk_stats
                }
    
    def _export_uncompressed(self, output_path: Path, handler: ExportHandler, options: ExportOptions) -> Dict[str, Any]:
        """Export without compression."""
        mode = 'w' if options.output_format != OutputFormat.BINARY else 'wb'
        
        with self._open_file(output_path, mode) as output:
            items = self._get_export_items(options)
            return handler.export_collection(items, output, options)
    
    def _export_compressed(self, output_path: Path, handler: ExportHandler, options: ExportOptions) -> Dict[str, Any]:
        """Export with compression."""
        temp_path = output_path.with_suffix('.tmp')
        
        # Export to temporary file first
        uncompressed_stats = self._export_uncompressed(temp_path, handler, options)
        
        # Compress
        with self.profiler.profile(f'compression_{options.compression.value}'):
            compressed_size = self._compress_file(temp_path, output_path, options.compression)
        
        # Cleanup and calculate ratio
        uncompressed_size = temp_path.stat().st_size
        temp_path.unlink()
        
        compression_ratio = uncompressed_size / compressed_size if compressed_size > 0 else 1.0
        
        uncompressed_stats.update({
            'uncompressed_size': uncompressed_size,
            'compressed_size': compressed_size,
            'compression_ratio': compression_ratio
        })
        
        return uncompressed_stats
    
    def _get_export_items(self, options: ExportOptions) -> Iterator[Any]:
        """Get items to export based on source type."""
        handler = self.handlers[options.output_format]
        
        if isinstance(self.source, TSNode):
            yield handler.export_node(self.source, options)
        
        elif isinstance(self.source, NodeGroup):
            for node in self.source:
                yield handler.export_node(node, options)
        
        elif isinstance(self.source, BatchResult):
            for file_result in self.source.files:
                if file_result.success and file_result.node:
                    yield handler.export_node(file_result.node, options)
                else:
                    # Export error information
                    yield {
                        'path': str(file_result.path),
                        'success': False,
                        'error': file_result.error,
                        'parse_time': file_result.parse_time
                    }
        
        elif isinstance(self.source, list):
            for item in self.source:
                if isinstance(item, TSNode):
                    yield handler.export_node(item, options)
                else:
                    yield item
        
        else:
            raise ValueError(f"Unsupported source type: {self.source_type}")
    
    def _chunk_items(self, items: Iterator[Any], chunk_size: int) -> Iterator[List[Any]]:
        """Chunk items for streaming processing."""
        chunk = []
        for item in items:
            chunk.append(item)
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []
        
        if chunk:
            yield chunk
    
    def _compress_file(self, input_path: Path, output_path: Path, compression: CompressionType) -> int:
        """Compress file using specified algorithm."""
        input_data = input_path.read_bytes()
        
        if compression == CompressionType.GZIP:
            compressed_data = gzip.compress(input_data, compresslevel=6)
        elif compression == CompressionType.LZ4:
            compressed_data = lz4.frame.compress(input_data, compression_level=3)
        elif compression == CompressionType.ZSTD:
            cctx = zstd.ZstdCompressor(level=3)
            compressed_data = cctx.compress(input_data)
        else:
            raise ValueError(f"Unsupported compression: {compression}")
        
        output_path.write_bytes(compressed_data)
        return len(compressed_data)
    
    @contextmanager
    def _open_output_file(self, path: Path, options: ExportOptions):
        """Context manager for output file handling."""
        mode = 'w' if options.output_format != OutputFormat.BINARY else 'wb'
        encoding = 'utf-8' if mode == 'w' else None
        
        with open(path, mode, encoding=encoding) as f:
            yield f
    
    def _open_file(self, path: Path, mode: str):
        """Open file with appropriate encoding."""
        encoding = 'utf-8' if 'b' not in mode else None
        return open(path, mode, encoding=encoding)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get export statistics."""
        return self._stats.copy()


# Utility functions for common export patterns
def export_single_node(node: TSNode, output_path: Path, 
                      format: ExportFormat = ExportFormat.FULL,
                      output_format: OutputFormat = OutputFormat.JSON) -> Dict[str, Any]:
    """Export single node with default options."""
    options = ExportOptions(format=format, output_format=output_format)
    engine = ExportEngine(node)
    return engine.export_to_file(output_path, options)


def export_batch_results(results: BatchResult, output_path: Path,
                        include_errors: bool = True) -> Dict[str, Any]:
    """Export batch results optimized for analysis."""
    options = ExportOptions(
        format=ExportFormat.METRICS,
        output_format=OutputFormat.JSONL,
        compression=CompressionType.LZ4,
        streaming=True
    )
    
    engine = ExportEngine(results)
    return engine.export_to_file(output_path, options)


def export_collection_streaming(nodes: NodeGroup, output_path: Path,
                               chunk_size: int = 1000) -> Iterator[Dict[str, Any]]:
    """Stream export large node collections."""
    options = ExportOptions(
        format=ExportFormat.CLEAN,
        output_format=OutputFormat.JSONL,
        streaming=True,
        chunk_size=chunk_size
    )
    
    engine = ExportEngine(nodes)
    yield from engine.stream_export(output_path, options)
