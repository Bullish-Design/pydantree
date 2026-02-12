from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pydantree.models.log_events import (
    GenerationCompletedEvent,
    GenerationFailedEvent,
    IngestCompletedEvent,
    IngestStartedEvent,
    NormalizeCompletedEvent,
    QueryRuntimeExecutionEvent,
    ToolVersions,
    ValidationCompletedEvent,
    ValidationFailedEvent,
    WorkshopEvent,
)


def resolve_tool_versions() -> ToolVersions:
    return ToolVersions(
        pydantree=_safe_version("pydantree"),
        pydantic=_safe_version("pydantic"),
        tree_sitter=_safe_version("tree-sitter"),
    )


def _safe_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "unknown"


class WorkshopEventLogger:
    def __init__(self, log_path: Path | str = Path("logs/workshop.jsonl")) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: WorkshopEvent) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json())
            handle.write("\n")

    def ingest_started(self, **kwargs: object) -> None:
        self.emit(IngestStartedEvent(**kwargs))

    def ingest_completed(self, **kwargs: object) -> None:
        self.emit(IngestCompletedEvent(**kwargs))

    def normalize_completed(self, **kwargs: object) -> None:
        self.emit(NormalizeCompletedEvent(**kwargs))

    def generation_completed(self, **kwargs: object) -> None:
        self.emit(GenerationCompletedEvent(**kwargs))

    def generation_failed(self, **kwargs: object) -> None:
        self.emit(GenerationFailedEvent(**kwargs))

    def validation_completed(self, **kwargs: object) -> None:
        self.emit(ValidationCompletedEvent(**kwargs))

    def validation_failed(self, **kwargs: object) -> None:
        self.emit(ValidationFailedEvent(**kwargs))

    def query_runtime_execution(self, **kwargs: object) -> None:
        self.emit(QueryRuntimeExecutionEvent(**kwargs))
