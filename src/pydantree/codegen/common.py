from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ValidationError


class CodegenDiagnosticError(Exception):
    """Error raised when a pipeline stage cannot continue with actionable context."""

    def __init__(self, stage: str, message: str, *, hint: str | None = None) -> None:
        self.stage = stage
        self.message = message
        self.hint = hint
        rendered = f"[{stage}] {message}"
        if hint:
            rendered = f"{rendered} Hint: {hint}"
        super().__init__(rendered)


def read_model(path: Path, model_type: type[BaseModel]) -> BaseModel:
    """Load and validate a Pydantic model from disk with diagnostics."""

    try:
        payload = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CodegenDiagnosticError(
            "io",
            f"Input file does not exist: {path}",
            hint="Provide a valid --input/--ingest/--normalize/--emit path.",
        ) from exc

    try:
        return model_type.model_validate_json(payload)
    except ValidationError as exc:
        raise CodegenDiagnosticError(
            "io",
            f"Could not parse {path} as {model_type.__name__}: {exc}",
            hint="Verify you passed the correct stage artifact as input.",
        ) from exc


def write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
