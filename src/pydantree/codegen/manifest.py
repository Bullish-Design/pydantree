from __future__ import annotations

import platform
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from pydantree.codegen.emit import EmitOutput
from pydantree.codegen.ingest import IngestOutput
from pydantree.codegen.normalize import NormalizeOutput


class ReproducibilityManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_hashes: dict[str, str]
    toolchain_versions: dict[str, str]
    output_file_hashes: dict[str, str]
    generated_at: datetime


def build_manifest(ingest: IngestOutput, normalize: NormalizeOutput, emit: EmitOutput) -> ReproducibilityManifest:
    del normalize

    input_hashes = {query.provenance.file_path: query.provenance.source_sha256 for query in ingest.queries}
    output_file_hashes = {module.file_path: module.content_sha256 for module in emit.modules}

    return ReproducibilityManifest(
        input_hashes=dict(sorted(input_hashes.items())),
        toolchain_versions={
            "python": platform.python_version(),
            "pydantree.codegen": "1",
        },
        output_file_hashes=dict(sorted(output_file_hashes.items())),
        generated_at=datetime.now(UTC),
    )
