from __future__ import annotations

import json
from pathlib import Path

from pydantree.codegen import cli
from pydantree.registry import WorkshopLayout
from pydantree.runtime import WorkshopEventLogger


def test_cli_name_contract_pipeline_via_parsed_args(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "pydantree"\n', encoding="utf-8")

    layout = WorkshopLayout.from_path(tmp_path)
    query_dir = layout.queries_pack_dir("python", "minimal_pack")
    query_dir.mkdir(parents=True)
    (query_dir / "highlights.scm").write_text("(identifier) @id\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    parser = cli._build_parser()

    for argv in (
        ["ingest", "python", "minimal_pack"],
        ["normalize", "python", "minimal_pack"],
        ["emit", "python", "minimal_pack"],
        ["manifest", "python", "minimal_pack"],
    ):
        args = parser.parse_args(argv)
        cli._dispatch(args, logger=WorkshopEventLogger(), run_id="test-run")

    ingest_path = tmp_path / "build" / "python" / "minimal_pack" / "ingest.json"
    emit_path = tmp_path / "build" / "python" / "minimal_pack" / "emit.json"
    ir_path = layout.ir_file("python", "minimal_pack")
    models_dir = layout.generated_models_dir("python", "minimal_pack")
    manifest_path = layout.manifest_file("python", "minimal_pack")

    assert ingest_path.exists()
    assert emit_path.exists()
    assert ir_path.exists()
    assert manifest_path.exists()
    generated_modules = list(models_dir.glob("*_highlights_models.py"))
    assert generated_modules

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["query_count"] == 1
