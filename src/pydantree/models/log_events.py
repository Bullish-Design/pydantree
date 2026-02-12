from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ToolVersions(BaseModel):
    pydantree: str
    pydantic: str
    tree_sitter: str


class LogContext(BaseModel):
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    language: str
    query_pack: str
    source_hash: str
    tool_versions: ToolVersions


class BaseLogEvent(LogContext):
    event: str


class IngestStartedEvent(BaseLogEvent):
    event: Literal["ingest.started"] = "ingest.started"


class IngestCompletedEvent(BaseLogEvent):
    event: Literal["ingest.completed"] = "ingest.completed"
    files_discovered: int = Field(ge=0)


class NormalizeCompletedEvent(BaseLogEvent):
    event: Literal["normalize.completed"] = "normalize.completed"
    records_normalized: int = Field(ge=0)


class GenerationCompletedEvent(BaseLogEvent):
    event: Literal["generation.completed"] = "generation.completed"
    models_generated: int = Field(ge=0)


class GenerationFailedEvent(BaseLogEvent):
    event: Literal["generation.failed"] = "generation.failed"
    error: str


class ValidationCompletedEvent(BaseLogEvent):
    event: Literal["validation.completed"] = "validation.completed"
    checks_run: int = Field(ge=0)


class ValidationFailedEvent(BaseLogEvent):
    event: Literal["validation.failed"] = "validation.failed"
    error: str


class QueryRuntimeExecutionEvent(BaseLogEvent):
    event: Literal["query.runtime.execution"] = "query.runtime.execution"
    target: str
    elapsed_ms: int = Field(ge=0)


WorkshopEvent = (
    IngestStartedEvent
    | IngestCompletedEvent
    | NormalizeCompletedEvent
    | GenerationCompletedEvent
    | GenerationFailedEvent
    | ValidationCompletedEvent
    | ValidationFailedEvent
    | QueryRuntimeExecutionEvent
)
