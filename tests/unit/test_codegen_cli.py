from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from pydantree.codegen.cli import _build_parser, _dispatch
from datetime import UTC, datetime

from pydantree.codegen.ingest import IngestOutput, IngestedQuery, QueryProvenance


class _LoggerSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def ingest_started(self, context) -> None:
        self.calls.append(("ingest_started", context))

    def ingest_completed(self, context, files_discovered: int) -> None:
        self.calls.append(("ingest_completed", files_discovered))

    def normalize_completed(self, context, records_normalized: int) -> None:
        self.calls.append(("normalize_completed", records_normalized))

    def generation_completed(self, context, models_generated: int) -> None:
        self.calls.append(("generation_completed", models_generated))

    def generation_failed(self, context, error: str) -> None:
        self.calls.append(("generation_failed", error))


def test_build_parser_ingest_requires_language_and_query_pack() -> None:
    parser = _build_parser()
    args = parser.parse_args(["ingest", "python", "core"])

    assert args.command == "ingest"
    assert args.language == "python"
    assert args.query_pack == "core"


def test_dispatch_ingest_uses_layout_defaults_and_logging(monkeypatch, tmp_path: Path) -> None:
    layout_root = tmp_path / "repo"
    logger = _LoggerSpy()
    args = Namespace(command="ingest", language="python", query_pack="core", out=None, pattern="*.scm")

    class _Layout:
        repository_root = layout_root

        def queries_pack_dir(self, *, language: str, query_pack: str) -> Path:
            assert language == "python"
            assert query_pack == "core"
            return layout_root / "workshop" / "queries" / language / query_pack

    ingest_payload = IngestOutput(
        root_dir="/tmp/queries",
        pattern="*.scm",
        queries=(
            IngestedQuery(
                provenance=QueryProvenance(
                    file_path="python/core/highlights.scm",
                    language="python",
                    query_type="highlights",
                    source_sha256="a" * 64,
                    source_bytes=10,
                    discovered_at=datetime.now(UTC),
                ),
                source_text="(identifier) @id",
            ),
        )
    )

    captured: dict[str, object] = {}

    monkeypatch.setattr("pydantree.codegen.cli._layout", lambda: _Layout())
    monkeypatch.setattr("pydantree.codegen.cli.hash_for_path", lambda path: "sha256:root")
    monkeypatch.setattr("pydantree.codegen.cli.ingest_scm", lambda root_dir, pattern: ingest_payload)

    def _write_model(path, payload) -> None:
        captured["path"] = path
        captured["payload"] = payload

    monkeypatch.setattr("pydantree.codegen.cli.write_model", _write_model)

    _dispatch(args, logger=logger, run_id="run-1")

    assert captured["path"] == layout_root / "build" / "ingest.python.core.json"
    assert captured["payload"] == ingest_payload
    assert logger.calls[0][0] == "ingest_started"
    assert logger.calls[1] == ("ingest_completed", 1)


def test_dispatch_normalize_uses_default_input_and_output_paths(monkeypatch, tmp_path: Path) -> None:
    layout_root = tmp_path / "repo"
    logger = _LoggerSpy()
    args = Namespace(command="normalize", language="python", query_pack="core", input_path=None, out=None)

    class _Layout:
        repository_root = layout_root

        def ir_file(self, *, language: str, query_pack: str) -> Path:
            assert language == "python"
            assert query_pack == "core"
            return layout_root / "workshop" / "ir" / language / query_pack / "ir.v1.json"

    ingest_payload = IngestOutput(
        root_dir="/tmp/queries",
        pattern="*.scm",
        queries=(
            IngestedQuery(
                provenance=QueryProvenance(
                    file_path="python/core/highlights.scm",
                    language="python",
                    query_type="highlights",
                    source_sha256="b" * 64,
                    source_bytes=10,
                    discovered_at=datetime.now(UTC),
                ),
                source_text="(identifier) @id",
            ),
        )
    )

    captured: dict[str, object] = {}

    monkeypatch.setattr("pydantree.codegen.cli._layout", lambda: _Layout())
    monkeypatch.setattr("pydantree.codegen.cli.hash_for_path", lambda path: "sha256:ingest")
    monkeypatch.setattr("pydantree.codegen.cli.read_model", lambda path, model: ingest_payload.model_dump(mode="json"))

    class _Normalized:
        queries = [object(), object()]

    monkeypatch.setattr("pydantree.codegen.cli.normalize_ingested", lambda ingest: _Normalized())

    def _write_model(path, payload) -> None:
        captured["path"] = path
        captured["payload"] = payload

    monkeypatch.setattr("pydantree.codegen.cli.write_model", _write_model)

    _dispatch(args, logger=logger, run_id="run-2")

    assert captured["path"] == layout_root / "workshop" / "ir" / "python" / "core" / "ir.v1.json"
    assert logger.calls[-1] == ("normalize_completed", 2)
