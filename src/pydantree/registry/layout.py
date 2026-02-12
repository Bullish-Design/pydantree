"""Path resolution helpers for the canonical workshop layout.

The layout keeps generated artifacts deterministic and discoverable while allowing
callers to resolve files by logical names (`language`, `query_pack`) only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_IR_FILENAME = "ir.v1.json"
_WORKSHOP_LOG_FILENAME = "workshop.jsonl"


class InvalidLayoutNameError(ValueError):
    """Raised when a language or query pack name is unsafe for filesystem layout."""



def _validate_name_segment(value: str, field_name: str) -> str:
    """Validate and normalize a layout segment.

    Names are intentionally conservative so all generated paths stay inside the
    expected repository layout.
    """

    segment = value.strip()
    if not segment:
        raise InvalidLayoutNameError(f"{field_name} must not be empty")

    forbidden = {".", ".."}
    if segment in forbidden:
        raise InvalidLayoutNameError(f"{field_name} must not be '.' or '..'")

    if "/" in segment or "\\" in segment:
        raise InvalidLayoutNameError(f"{field_name} must not contain path separators")

    return segment


@dataclass(frozen=True)
class WorkshopLayout:
    """Resolver for canonical pydantree workspace paths.

    Canonical paths (from repository root):
    - workshop/queries/<language>/<query_pack>/*.scm
    - workshop/ir/<language>/<query_pack>/ir.v1.json
    - src/pydantree/generated/<language>/<query_pack>/
    - workshop/manifests/<language>/<query_pack>.json
    - logs/workshop.jsonl
    """

    repository_root: Path

    @classmethod
    def from_path(cls, repository_root: Path | str) -> "WorkshopLayout":
        """Create a layout resolver rooted at a repository path."""

        return cls(repository_root=Path(repository_root).resolve())

    def _names(self, language: str, query_pack: str) -> tuple[str, str]:
        return (
            _validate_name_segment(language, "language"),
            _validate_name_segment(query_pack, "query_pack"),
        )

    def queries_pack_dir(self, language: str, query_pack: str) -> Path:
        """Return the source-of-truth query pack directory."""

        language_name, pack_name = self._names(language, query_pack)
        return self.repository_root / "workshop" / "queries" / language_name / pack_name

    def query_file(self, language: str, query_pack: str, filename: str) -> Path:
        """Return a `.scm` source query file under the canonical query pack path."""

        safe_filename = _validate_name_segment(filename, "filename")
        if not safe_filename.endswith(".scm"):
            raise InvalidLayoutNameError("filename must end with '.scm'")

        return self.queries_pack_dir(language=language, query_pack=query_pack) / safe_filename

    def ir_file(self, language: str, query_pack: str) -> Path:
        """Return the canonical IR path (`ir.v1.json`)."""

        language_name, pack_name = self._names(language, query_pack)
        return self.repository_root / "workshop" / "ir" / language_name / pack_name / _IR_FILENAME

    def generated_models_dir(self, language: str, query_pack: str) -> Path:
        """Return the canonical generated models directory."""

        language_name, pack_name = self._names(language, query_pack)
        return self.repository_root / "src" / "pydantree" / "generated" / language_name / pack_name

    def manifest_file(self, language: str, query_pack: str) -> Path:
        """Return the canonical generation manifest path."""

        language_name, pack_name = self._names(language, query_pack)
        manifest_name = f"{pack_name}.json"
        return self.repository_root / "workshop" / "manifests" / language_name / manifest_name

    def workshop_log_file(self) -> Path:
        """Return the canonical append-only workshop event log path."""

        return self.repository_root / "logs" / _WORKSHOP_LOG_FILENAME
