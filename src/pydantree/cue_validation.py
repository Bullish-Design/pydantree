from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    summary: str
    details: list[str]


class CueUnavailableError(RuntimeError):
    """Raised when the CUE CLI is not available."""


_PATTERN_CAPTURE_PATTERNS = [
    re.compile(r"patterns\[(\d+)\]\.captures\[(\d+)\]"),
    re.compile(r"patterns\.(\d+)\.captures\.(\d+)"),
]
_CAPTURE_PATTERNS = [re.compile(r"captures\[(\d+)\]"), re.compile(r"captures\.(\d+)")]


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _capture_context(
    ir_data: Any,
    capture_idx: int | None = None,
    pattern_idx: int | None = None,
    pattern_capture_idx: int | None = None,
) -> tuple[str | None, str | None]:
    if not isinstance(ir_data, dict):
        return (None, None)

    metadata = ir_data.get("query_metadata") or ir_data.get("metadata") or {}
    source_scm = metadata.get("source_scm") if isinstance(metadata, dict) else None

    patterns = ir_data.get("patterns") or ir_data.get("pattern") or []
    if isinstance(patterns, dict):
        patterns = [patterns]

    if pattern_idx is not None and pattern_capture_idx is not None and pattern_idx < len(patterns):
        pattern = patterns[pattern_idx]
        if isinstance(pattern, dict):
            captures = pattern.get("captures", [])
            if isinstance(captures, list) and pattern_capture_idx < len(captures):
                capture = captures[pattern_capture_idx]
                if isinstance(capture, dict):
                    capture_name = capture.get("name")
                    src = capture.get("source")
                    if isinstance(src, dict):
                        source_scm = src.get("file") or source_scm
                    if isinstance(capture_name, str):
                        return (source_scm, capture_name)

    captures: list[dict[str, Any]] = []
    for pattern in patterns:
        if not isinstance(pattern, dict):
            continue
        items = pattern.get("captures", [])
        if isinstance(items, list):
            captures.extend(item for item in items if isinstance(item, dict))

    if capture_idx is None or capture_idx >= len(captures):
        return (source_scm, None)

    capture = captures[capture_idx]
    capture_name = capture.get("name")
    src = capture.get("source")
    if isinstance(src, dict):
        source_scm = src.get("file") or source_scm

    return (source_scm, capture_name if isinstance(capture_name, str) else None)


def _map_context(line: str, ir_data: Any) -> str:
    for pattern in _PATTERN_CAPTURE_PATTERNS:
        match = pattern.search(line)
        if match:
            source_scm, capture_name = _capture_context(
                ir_data,
                pattern_idx=int(match.group(1)),
                pattern_capture_idx=int(match.group(2)),
            )
            context_parts = []
            if source_scm:
                context_parts.append(f"scm={source_scm}")
            if capture_name:
                context_parts.append(f"capture={capture_name}")
            if context_parts:
                return f"{line.strip()} [{' '.join(context_parts)}]"
            return line.strip()

    capture_idx: int | None = None
    for pattern in _CAPTURE_PATTERNS:
        match = pattern.search(line)
        if match:
            capture_idx = int(match.group(1))
            break

    if capture_idx is None:
        return line.strip()

    source_scm, capture_name = _capture_context(ir_data, capture_idx)
    context_parts = []
    if source_scm:
        context_parts.append(f"scm={source_scm}")
    if capture_name:
        context_parts.append(f"capture={capture_name}")

    if not context_parts:
        return line.strip()

    return f"{line.strip()} [{' '.join(context_parts)}]"


def run_cue_validation(data_file: Path, schema_file: Path) -> ValidationResult:
    if shutil.which("cue") is None:
        raise CueUnavailableError("CUE CLI not found in PATH.")

    completed = subprocess.run(
        ["cue", "vet", str(data_file), str(schema_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode == 0:
        return ValidationResult(ok=True, summary="validation passed", details=[])

    raw_lines = [line for line in completed.stderr.splitlines() if line.strip()]
    if not raw_lines:
        raw_lines = [line for line in completed.stdout.splitlines() if line.strip()]

    ir_data = _load_json(data_file)
    mapped = [_map_context(line, ir_data) for line in raw_lines[:5]]

    return ValidationResult(ok=False, summary="validation failed", details=mapped)
