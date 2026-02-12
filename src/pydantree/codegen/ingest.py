from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from pydantree.codegen.common import CodegenDiagnosticError


class QueryProvenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    file_path: str
    language: str
    query_type: str
    source_sha256: str
    discovered_at: datetime


class IngestedQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    provenance: QueryProvenance
    source_text: str


class IngestOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    root_dir: str
    pattern: str = Field(default="*.scm")
    queries: tuple[IngestedQuery, ...]


def ingest_scm(root_dir: Path, pattern: str = "*.scm") -> IngestOutput:
    if not root_dir.exists():
        raise CodegenDiagnosticError(
            "ingest",
            f"Root directory does not exist: {root_dir}",
            hint="Create the directory or point --root-dir at the generated queries path.",
        )
    if not root_dir.is_dir():
        raise CodegenDiagnosticError(
            "ingest",
            f"Root path is not a directory: {root_dir}",
            hint="Use a directory containing .scm query files.",
        )

    discovered: list[IngestedQuery] = []
    for scm_file in sorted(root_dir.rglob(pattern)):
        if scm_file.suffix != ".scm":
            continue
        source_text = scm_file.read_text(encoding="utf-8")
        rel_path = scm_file.relative_to(root_dir)
        language, query_type = _derive_query_metadata(rel_path)
        discovered.append(
            IngestedQuery(
                provenance=QueryProvenance(
                    file_path=rel_path.as_posix(),
                    language=language,
                    query_type=query_type,
                    source_sha256=sha256(source_text.encode("utf-8")).hexdigest(),
                    discovered_at=datetime.now(UTC),
                ),
                source_text=source_text,
            )
        )

    if not discovered:
        raise CodegenDiagnosticError(
            "ingest",
            f"No query files matching pattern '{pattern}' found under {root_dir}",
            hint="Check the folder layout or pass a broader --pattern value.",
        )

    return IngestOutput(root_dir=root_dir.as_posix(), pattern=pattern, queries=tuple(discovered))


def _derive_query_metadata(relative_path: Path) -> tuple[str, str]:
    parts = relative_path.parts
    if len(parts) == 1:
        return "unknown", relative_path.stem
    return parts[-2], relative_path.stem
