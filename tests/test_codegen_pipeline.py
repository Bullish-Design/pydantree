from __future__ import annotations

from pathlib import Path

import pytest

from pydantree.codegen.common import CodegenDiagnosticError
from pydantree.codegen.emit import emit_models
from pydantree.codegen.ingest import ingest_scm
from pydantree.codegen.manifest import build_manifest
from pydantree.codegen.normalize import normalize_ingested


def test_pipeline_roundtrip(tmp_path: Path) -> None:
    query_dir = tmp_path / "queries" / "python"
    query_dir.mkdir(parents=True)
    (query_dir / "highlights.scm").write_text("(function_definition name: (identifier) @function.name)\n", encoding="utf-8")

    ingest = ingest_scm(tmp_path / "queries")
    normalize = normalize_ingested(ingest)
    emit = emit_models(normalize, tmp_path / "generated")
    manifest = build_manifest(ingest, normalize, emit)

    assert len(ingest.queries) == 1
    assert len(normalize.queries[0].patterns) == 1
    assert len(emit.modules) == 1
    assert manifest.query_count == 1
    assert (tmp_path / "generated" / "python_highlights_models.py").exists()


def test_ingest_fails_without_scm(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(CodegenDiagnosticError, match="No query files matching pattern"):
        ingest_scm(empty)
