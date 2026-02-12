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
    assert ingest.queries[0].provenance.source_bytes > 0
    assert len(normalize.queries[0].patterns) == 1
    assert normalize.queries[0].patterns[0].ordinal == 1
    assert len(emit.modules) == 1
    assert manifest.input_hashes["python/highlights.scm"] == ingest.queries[0].provenance.source_sha256
    assert len(manifest.output_file_hashes) == 1
    assert manifest.query_count == 1
    assert manifest.module_count == 1
    assert manifest.pipeline_version == "2"
    assert len(manifest.ingest_fingerprint) == 64
    assert len(manifest.normalize_fingerprint) == 64
    assert len(manifest.emit_fingerprint) == 64
    assert (tmp_path / "generated" / "python_highlights_models.py").exists()


def test_ingest_fails_without_scm(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(CodegenDiagnosticError, match="No query files matching pattern"):
        ingest_scm(empty)


def test_ingest_fails_on_empty_scm_file(tmp_path: Path) -> None:
    query_dir = tmp_path / "queries"
    query_dir.mkdir(parents=True)
    (query_dir / "empty.scm").write_text("\n", encoding="utf-8")

    with pytest.raises(CodegenDiagnosticError, match="Query file is empty"):
        ingest_scm(query_dir)


def test_manifest_fails_with_mismatched_emit_payload(tmp_path: Path) -> None:
    query_dir = tmp_path / "queries" / "python"
    query_dir.mkdir(parents=True)
    (query_dir / "highlights.scm").write_text("(identifier) @id\n", encoding="utf-8")

    ingest = ingest_scm(tmp_path / "queries")
    normalize = normalize_ingested(ingest)
    emit = emit_models(normalize, tmp_path / "generated")

    with pytest.raises(CodegenDiagnosticError, match="Normalize and emit counts do not match"):
        build_manifest(ingest, normalize, emit.model_copy(update={"modules": tuple()}))


def test_manifest_fails_with_mismatched_normalize_payload(tmp_path: Path) -> None:
    query_dir = tmp_path / "queries" / "python"
    query_dir.mkdir(parents=True)
    (query_dir / "highlights.scm").write_text("(identifier) @id\n", encoding="utf-8")

    ingest = ingest_scm(tmp_path / "queries")
    normalize = normalize_ingested(ingest)
    emit = emit_models(normalize, tmp_path / "generated")

    with pytest.raises(CodegenDiagnosticError, match="Ingest and normalize query counts do not match"):
        build_manifest(ingest, normalize.model_copy(update={"queries": tuple()}), emit)


def test_manifest_serialized_contract_keys_and_types(tmp_path: Path) -> None:
    query_dir = tmp_path / "queries" / "python"
    query_dir.mkdir(parents=True)
    (query_dir / "highlights.scm").write_text("(identifier) @id\n", encoding="utf-8")

    ingest = ingest_scm(tmp_path / "queries")
    normalize = normalize_ingested(ingest)
    emit = emit_models(normalize, tmp_path / "generated")

    payload = build_manifest(ingest, normalize, emit).model_dump(mode="json")

    assert set(payload) == {
        "pipeline_version",
        "input_hashes",
        "toolchain_versions",
        "output_file_hashes",
        "ingest_fingerprint",
        "normalize_fingerprint",
        "emit_fingerprint",
        "query_count",
        "module_count",
        "generated_at",
    }
    assert isinstance(payload["pipeline_version"], str)
    assert isinstance(payload["input_hashes"], dict)
    assert isinstance(payload["toolchain_versions"], dict)
    assert isinstance(payload["output_file_hashes"], dict)
    assert isinstance(payload["ingest_fingerprint"], str)
    assert isinstance(payload["normalize_fingerprint"], str)
    assert isinstance(payload["emit_fingerprint"], str)
    assert isinstance(payload["query_count"], int)
    assert isinstance(payload["module_count"], int)
    assert isinstance(payload["generated_at"], str)
