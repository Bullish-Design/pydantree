from __future__ import annotations

import json
import platform
from hashlib import sha256
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from pydantree.codegen.common import CodegenDiagnosticError
from pydantree.codegen.emit import EmitOutput
from pydantree.codegen.ingest import IngestOutput
from pydantree.codegen.normalize import NormalizeOutput


class ReproducibilityManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    pipeline_version: str
    input_hashes: dict[str, str]
    toolchain_versions: dict[str, str]
    output_file_hashes: dict[str, str]
    ingest_fingerprint: str
    normalize_fingerprint: str
    emit_fingerprint: str
    query_count: int
    module_count: int
    generated_at: datetime


def build_manifest(ingest: IngestOutput, normalize: NormalizeOutput, emit: EmitOutput) -> ReproducibilityManifest:
    input_hashes = {query.provenance.file_path: query.provenance.source_sha256 for query in ingest.queries}
    output_file_hashes = {module.file_path: module.content_sha256 for module in emit.modules}
    if len(ingest.queries) != len(normalize.queries):
        raise CodegenDiagnosticError(
            "manifest",
            "Ingest and normalize query counts do not match.",
            hint="Ensure normalize was produced from the same ingest artifact.",
        )
    if len(normalize.queries) != len(emit.modules):
        raise CodegenDiagnosticError(
            "manifest",
            "Normalize and emit counts do not match.",
            hint="Ensure emit was produced from the same normalize artifact.",
        )

    return ReproducibilityManifest(
        pipeline_version="2",
        input_hashes=dict(sorted(input_hashes.items())),
        toolchain_versions={
            "python": platform.python_version(),
            "pydantree.codegen": "1",
        },
        output_file_hashes=dict(sorted(output_file_hashes.items())),
        ingest_fingerprint=_fingerprint(ingest.model_dump(mode="json")),
        normalize_fingerprint=_fingerprint(normalize.model_dump(mode="json")),
        emit_fingerprint=_fingerprint(emit.model_dump(mode="json")),
        query_count=len(normalize.queries),
        module_count=len(emit.modules),
        generated_at=datetime.now(UTC),
    )


def _fingerprint(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()
