from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from pydantic import BaseModel, ConfigDict

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
    return ReproducibilityManifest(
        generated_at=datetime.now(UTC),
        pipeline_version="1",
        ingest_fingerprint=_fingerprint(ingest.model_dump_json()),
        normalize_fingerprint=_fingerprint(normalize.model_dump_json()),
        emit_fingerprint=_fingerprint(emit.model_dump_json()),
        query_count=len(normalize.queries),
        module_count=len(emit.modules),
    )


def _fingerprint(payload: str) -> str:
    return sha256(payload.encode("utf-8")).hexdigest()
