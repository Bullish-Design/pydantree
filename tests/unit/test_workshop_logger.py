from __future__ import annotations

import json

from pydantree.runtime import WorkshopEventLogger, build_log_context


def _base_context():
    return build_log_context(
        run_id="run-123",
        language="python",
        query_pack="core",
        source_hash="sha256:abc",
    )


def test_logger_emits_all_workshop_events(tmp_path) -> None:
    logger = WorkshopEventLogger(tmp_path / "logs/workshop.jsonl")
    context = _base_context()

    logger.ingest_started(context)
    logger.ingest_completed(context, files_discovered=2)
    logger.normalize_completed(context, records_normalized=2)
    logger.generation_completed(context, models_generated=1)
    logger.generation_failed(context, error="codegen failed")
    logger.validation_completed(context, checks_run=8)
    logger.validation_failed(context, error="schema invalid")
    logger.query_runtime_execution(context, target="fixtures/example.py", elapsed_ms=42)

    lines = (tmp_path / "logs/workshop.jsonl").read_text(encoding="utf-8").strip().splitlines()

    assert len(lines) == 8

    events = [json.loads(line) for line in lines]

    assert [event["event"] for event in events] == [
        "ingest.started",
        "ingest.completed",
        "normalize.completed",
        "generation.completed",
        "generation.failed",
        "validation.completed",
        "validation.failed",
        "query.runtime.execution",
    ]
    assert all(event["run_id"] == "run-123" for event in events)
    assert all("timestamp" in event for event in events)


def test_logger_uses_canonical_default_log_path(monkeypatch, tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname=\"pydantree\"\n", encoding="utf-8")
    nested = tmp_path / "subdir"
    nested.mkdir()
    monkeypatch.chdir(nested)

    logger = WorkshopEventLogger()

    assert logger.log_path == tmp_path / "logs/workshop.jsonl"
