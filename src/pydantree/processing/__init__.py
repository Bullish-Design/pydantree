# pydantree/processing/__init__.py
"""Tools for processing collections of nodes and files."""

from .collections import (
    NodeGroup,
    NodeSelector,
    TypeSelector,
    ClassSelector,
    PredicateSelector,
    nodes,
    from_tree,
)
from .batch import (
    BatchProcessor,
    FileResult,
    BatchResult,
    ProcessingMode,
    ProcessingPriority,
    discover_source_files,
    batch_processing_session,
)

__all__ = [
    "NodeGroup",
    "NodeSelector",
    "TypeSelector",
    "ClassSelector",
    "PredicateSelector",
    "nodes",
    "from_tree",
    "BatchProcessor",
    "FileResult",
    "BatchResult",
    "ProcessingMode",
    "ProcessingPriority",
    "discover_source_files",
    "batch_processing_session",
]
