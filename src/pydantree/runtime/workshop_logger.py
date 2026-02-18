from __future__ import annotations

from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pydantree.models.log_events import (
    GenerationCompletedEvent,
    GenerationFailedEvent,
    IngestCompletedEvent,
    IngestStartedEvent,
    LogContext,
    NormalizeCompletedEvent,
    QueryRuntimeExecutionEvent,
    ToolVersions,
    ValidationCompletedEvent,
    ValidationFailedEvent,
    WorkshopEvent,
)
from pydantree.registry import WorkshopLayout, resolve_repository_root


def resolve_tool_versions() -> ToolVersions:
    return ToolVersions(
        pydantree=_safe_version("pydantree"),
        pydantic=_safe_version("pydantic"),
        tree_sitter=_safe_version("tree-sitter"),
    )


def build_log_context(*, run_id: str, language: str, query_pack: str, source_hash: str) -> LogContext:
    return LogContext(
        run_id=run_id,
        language=language,
        query_pack=query_pack,
        source_hash=source_hash,
        tool_versions=resolve_tool_versions(),
    )


def hash_for_path(path: Path) -> str:
    if path.is_file():
        return f"sha256:{sha256(path.read_bytes()).hexdigest()}"

    if path.is_dir():
        digest = sha256()
        for nested in sorted(path.rglob("*")):
            if nested.is_file():
                digest.update(nested.relative_to(path).as_posix().encode("utf-8"))
                digest.update(b"\n")
                digest.update(nested.read_bytes())
                digest.update(b"\n")
        return f"sha256:{digest.hexdigest()}"

    return "sha256:unknown"


def _safe_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "unknown"


class WorkshopEventLogger:
    def __init__(self, log_path: Path | str | None = None) -> None:
        if log_path is None:
            layout = WorkshopLayout.from_path(resolve_repository_root())
            self.log_path = layout.workshop_log_file()
        else:
            self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: WorkshopEvent) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json())
            handle.write("\n")

    def ingest_started(self, context: LogContext) -> None:
        self.emit(IngestStartedEvent(**context.model_dump()))

    def ingest_completed(self, context: LogContext, files_discovered: int) -> None:
        self.emit(IngestCompletedEvent(**context.model_dump(), files_discovered=files_discovered))

    def normalize_completed(self, context: LogContext, records_normalized: int) -> None:
        self.emit(NormalizeCompletedEvent(**context.model_dump(), records_normalized=records_normalized))

    def generation_completed(self, context: LogContext, models_generated: int) -> None:
        self.emit(GenerationCompletedEvent(**context.model_dump(), models_generated=models_generated))

    def generation_failed(self, context: LogContext, error: str) -> None:
        self.emit(GenerationFailedEvent(**context.model_dump(), error=error))

    def validation_completed(self, context: LogContext, checks_run: int) -> None:
        self.emit(ValidationCompletedEvent(**context.model_dump(), checks_run=checks_run))

    def validation_failed(self, context: LogContext, error: str) -> None:
        self.emit(ValidationFailedEvent(**context.model_dump(), error=error))

    def query_runtime_execution(self, context: LogContext, target: str, elapsed_ms: int) -> None:
        self.emit(QueryRuntimeExecutionEvent(**context.model_dump(), target=target, elapsed_ms=elapsed_ms))
