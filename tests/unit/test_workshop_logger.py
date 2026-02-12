from __future__ import annotations

import json

from pydantree.runtime import WorkshopEventLogger


def _base_payload() -> dict[str, object]:
    return {
        "run_id": "run-123",
        "language": "python",
        "query_pack": "core",
        "source_hash": "sha256:abc",
        "tool_versions": {
            "pydantree": "0.1.0",
            "pydantic": "2.11.0",
            "tree_sitter": "0.23.0",
        },
    }


def test_logger_emits_all_workshop_events(tmp_path) -> None:
    logger = WorkshopEventLogger(tmp_path / "logs/workshop.jsonl")
    payload = _base_payload()

    logger.ingest_started(**payload)
    logger.ingest_completed(**payload, files_discovered=2)
    logger.normalize_completed(**payload, records_normalized=2)
    logger.generation_completed(**payload, models_generated=1)
    logger.generation_failed(**payload, error="codegen failed")
    logger.validation_completed(**payload, checks_run=8)
    logger.validation_failed(**payload, error="schema invalid")
    logger.query_runtime_execution(**payload, target="fixtures/example.py", elapsed_ms=42)

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
