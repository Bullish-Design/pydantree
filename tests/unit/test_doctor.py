from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantree.doctor import format_human_summary, run_doctor


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_doctor_detects_empty_invalid_and_unsupported(tmp_path: Path) -> None:
    queries = tmp_path / "queries"
    queries.mkdir()

    (queries / "empty.scm").write_text("\n", encoding="utf-8")
    (queries / "bad.scm").write_text("(identifier) @ok\n(string) @bad! #offset!", encoding="utf-8")

    result = run_doctor(repo_root=tmp_path, queries_dir=queries, manifest_path=tmp_path / "missing.json")

    codes = {issue["code"] for issue in result["issues"]}
    assert "scm.empty_file" in codes
    assert "capture.invalid_name" in codes
    assert "capture.duplicate_in_file" not in codes
    assert "query.unsupported_feature" in codes
    assert "manifest.not_found" in codes


def test_doctor_detects_duplicate_capture_names_in_file(tmp_path: Path) -> None:
    queries = tmp_path / "queries"
    queries.mkdir()
    (queries / "dup.scm").write_text("(identifier) @name (string) @name", encoding="utf-8")

    result = run_doctor(repo_root=tmp_path, queries_dir=queries, manifest_path=tmp_path / "missing.json")

    duplicate_issues = [issue for issue in result["issues"] if issue["code"] == "capture.duplicate_in_file"]
    assert len(duplicate_issues) == 1
    assert duplicate_issues[0]["file"] == "queries/dup.scm"


def test_doctor_checks_manifest_and_generation_hashes(tmp_path: Path) -> None:
    queries = tmp_path / "queries"
    queries.mkdir()
    input_file = queries / "highlights.scm"
    input_contents = "(identifier) @name"
    input_file.write_text(input_contents, encoding="utf-8")

    generated = tmp_path / "generated.py"
    generated.write_text("print('a')\n", encoding="utf-8")

    manifest = {
        "input_hashes": {"queries/highlights.scm": "wrong"},
        "output_file_hashes": {"generated.py": "also-wrong"},
    }
    manifest_path = tmp_path / "generated" / "manifest.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_doctor(repo_root=tmp_path, queries_dir=queries, manifest_path=manifest_path)
    codes = {issue["code"] for issue in result["issues"]}

    assert "manifest.input_hash_mismatch" in codes
    assert "generation.nondeterministic_diff" in codes

    manifest_ok = {
        "input_hashes": {"queries/highlights.scm": _sha(input_contents)},
        "output_file_hashes": {"generated.py": hashlib.sha256(generated.read_bytes()).hexdigest()},
    }
    manifest_path.write_text(json.dumps(manifest_ok), encoding="utf-8")
    result_ok = run_doctor(repo_root=tmp_path, queries_dir=queries, manifest_path=manifest_path)
    mismatch_codes = {
        issue["code"]
        for issue in result_ok["issues"]
        if issue["code"].startswith("manifest.") or issue["code"].startswith("generation.")
    }
    assert mismatch_codes == set()


def test_doctor_detects_missing_manifest_referenced_input_file(tmp_path: Path) -> None:
    queries = tmp_path / "queries"
    queries.mkdir()
    (queries / "highlights.scm").write_text("(identifier) @name", encoding="utf-8")

    manifest = {
        "input_hashes": {
            "queries/highlights.scm": _sha("(identifier) @name"),
            "queries/missing.scm": _sha("(string) @missing"),
        },
        "generated_hashes": {},
    }
    manifest_path = tmp_path / "generated" / "manifest.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_doctor(repo_root=tmp_path, queries_dir=queries, manifest_path=manifest_path)

    issues_by_code = {issue["code"] for issue in result["issues"]}
    assert "scm.missing_file" in issues_by_code
    assert "manifest.missing_input" in issues_by_code


def test_human_summary_renders() -> None:
    text = format_human_summary(
        {
            "ok": False,
            "summary": {"errors": 1, "warnings": 1, "scm_files": 2},
            "issues": [
                {"code": "x", "severity": "error", "message": "bad", "file": "queries/a.scm"},
                {"code": "y", "severity": "warning", "message": "warn", "file": None},
            ],
        }
    )

    assert "Doctor found issues" in text
    assert "queries/a.scm" in text
