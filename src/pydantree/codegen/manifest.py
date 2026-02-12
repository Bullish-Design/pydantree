from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256

from pydantic import BaseModel, ConfigDict

from pydantree.codegen.common import CodegenDiagnosticError
from pydantree.codegen.emit import EmitOutput
from pydantree.codegen.ingest import IngestOutput
from pydantree.codegen.normalize import NormalizeOutput


class ReproducibilityManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    pipeline_version: str
    ingest_fingerprint: str
    normalize_fingerprint: str
    emit_fingerprint: str
    query_count: int
    module_count: int


def build_manifest(ingest: IngestOutput, normalize: NormalizeOutput, emit: EmitOutput) -> ReproducibilityManifest:
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
        generated_at=datetime.now(UTC),
        pipeline_version="2",
        ingest_fingerprint=_fingerprint(ingest.model_dump(mode="json")),
        normalize_fingerprint=_fingerprint(normalize.model_dump(mode="json")),
        emit_fingerprint=_fingerprint(emit.model_dump(mode="json")),
        query_count=len(normalize.queries),
        module_count=len(emit.modules),
    )


def _fingerprint(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()
