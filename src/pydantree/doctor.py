from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_CAPTURE_PATTERN = re.compile(r"@([^\s\]\)\}\"']+)")
_VALID_CAPTURE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_UNSUPPORTED_QUERY_FEATURES = {
    "#offset!": "offset directives are not supported by pydantree codegen.",
    "#select-adjacent!": "adjacent-selection directives are not supported by pydantree codegen.",
    "#strip!": "strip directives are not supported by pydantree codegen.",
}


@dataclass(slots=True)
class DoctorIssue:
    code: str
    severity: str
    message: str
    file: str | None = None
    details: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _discover_scm_files(queries_dir: Path) -> list[Path]:
    if not queries_dir.exists():
        return []
    return sorted(path for path in queries_dir.rglob("*.scm") if path.is_file())


def run_doctor(repo_root: Path, queries_dir: Path, manifest_path: Path) -> dict[str, Any]:
    issues: list[DoctorIssue] = []

    scm_files = _discover_scm_files(queries_dir)
    if queries_dir.exists() and not scm_files:
        issues.append(
            DoctorIssue(
                code="scm.none_found",
                severity="warning",
                message=f"No .scm files were found under {queries_dir}.",
            )
        )

    capture_occurrences: dict[str, list[str]] = {}
    input_hashes: dict[str, str] = {}

    for scm_file in scm_files:
        rel = str(scm_file.relative_to(repo_root))
        content = scm_file.read_text(encoding="utf-8")
        input_hashes[rel] = _sha256_text(content)

        if not content.strip():
            issues.append(
                DoctorIssue(
                    code="scm.empty_file",
                    severity="error",
                    message="SCM file is empty.",
                    file=rel,
                )
            )

        for feature, reason in _UNSUPPORTED_QUERY_FEATURES.items():
            if feature in content:
                issues.append(
                    DoctorIssue(
                        code="query.unsupported_feature",
                        severity="error",
                        message=f"Unsupported query feature '{feature}' detected: {reason}",
                        file=rel,
                        details={"feature": feature},
                    )
                )

        for capture in _CAPTURE_PATTERN.findall(content):
            capture_occurrences.setdefault(capture, []).append(rel)
            if not _VALID_CAPTURE_PATTERN.fullmatch(capture):
                issues.append(
                    DoctorIssue(
                        code="capture.invalid_name",
                        severity="error",
                        message=f"Invalid capture name '{capture}'.",
                        file=rel,
                        details={"capture": capture},
                    )
                )

    for capture, files in sorted(capture_occurrences.items()):
        unique_files = sorted(set(files))
        if len(unique_files) > 1:
            issues.append(
                DoctorIssue(
                    code="capture.duplicate_name",
                    severity="warning",
                    message=(
                        f"Capture name '{capture}' is declared in multiple .scm files and may create ambiguous models."
                    ),
                    details={"capture": capture, "files": unique_files},
                )
            )

    tree_sitter_cli = shutil.which("tree-sitter")
    cue_cli = shutil.which("cue")
    if tree_sitter_cli is None:
        issues.append(
            DoctorIssue(
                code="dependency.missing_tree_sitter_cli",
                severity="error",
                message="Missing runtime dependency: `tree-sitter` CLI is not available on PATH.",
            )
        )
    if cue_cli is None:
        issues.append(
            DoctorIssue(
                code="dependency.missing_cue_cli",
                severity="error",
                message="Missing runtime dependency: `cue` CLI is not available on PATH.",
            )
        )

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_inputs = manifest.get("input_hashes", {})
        for rel, expected_hash in manifest_inputs.items():
            actual_hash = input_hashes.get(rel)
            if actual_hash is None:
                issues.append(
                    DoctorIssue(
                        code="manifest.missing_input",
                        severity="error",
                        message=f"Manifest references missing input file '{rel}'.",
                        file=rel,
                    )
                )
                continue
            if actual_hash != expected_hash:
                issues.append(
                    DoctorIssue(
                        code="manifest.input_hash_mismatch",
                        severity="error",
                        message=f"Manifest hash mismatch for '{rel}'.",
                        file=rel,
                        details={"expected": expected_hash, "actual": actual_hash},
                    )
                )

        for rel, expected_hash in manifest.get("generated_hashes", {}).items():
            generated_path = repo_root / rel
            if not generated_path.exists():
                issues.append(
                    DoctorIssue(
                        code="generation.missing_output",
                        severity="error",
                        message=f"Generated file declared in manifest is missing: '{rel}'.",
                        file=rel,
                    )
                )
                continue
            actual_hash = _sha256_file(generated_path)
            if actual_hash != expected_hash:
                issues.append(
                    DoctorIssue(
                        code="generation.nondeterministic_diff",
                        severity="error",
                        message=f"Generated output hash differs from manifest for '{rel}'.",
                        file=rel,
                        details={"expected": expected_hash, "actual": actual_hash},
                    )
                )
    else:
        issues.append(
            DoctorIssue(
                code="manifest.not_found",
                severity="warning",
                message=f"Generation manifest not found at {manifest_path}; hash checks skipped.",
            )
        )

    errors = sum(1 for issue in issues if issue.severity == "error")
    warnings = sum(1 for issue in issues if issue.severity == "warning")

    return {
        "ok": errors == 0,
        "summary": {
            "scm_files": len(scm_files),
            "errors": errors,
            "warnings": warnings,
        },
        "issues": [issue.as_dict() for issue in issues],
    }


def format_human_summary(result: dict[str, Any]) -> str:
    summary = result["summary"]
    header = (
        f"Doctor {'passed' if result['ok'] else 'found issues'}: "
        f"{summary['errors']} error(s), {summary['warnings']} warning(s), {summary['scm_files']} .scm file(s) checked."
    )
    lines = [header]
    for issue in result["issues"]:
        location = f" [{issue['file']}]" if issue.get("file") else ""
        lines.append(f"- {issue['severity'].upper()} {issue['code']}{location}: {issue['message']}")
    return "\n".join(lines)
