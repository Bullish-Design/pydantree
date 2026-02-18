from __future__ import annotations

import re
from hashlib import sha1

from pydantic import BaseModel, ConfigDict

from pydantree.codegen.common import CodegenDiagnosticError
from pydantree.codegen.ingest import IngestOutput, QueryProvenance

_CAPTURE_RE = re.compile(r"@([A-Za-z0-9_.-]+)")


class NormalizedCapture(BaseModel):
    model_config = ConfigDict(frozen=True)

    capture_id: str
    name: str


class NormalizedPattern(BaseModel):
    model_config = ConfigDict(frozen=True)

    ordinal: int
    pattern_id: str
    source: str
    captures: tuple[NormalizedCapture, ...]


class NormalizedQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    provenance: QueryProvenance
    patterns: tuple[NormalizedPattern, ...]


class NormalizeOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    queries: tuple[NormalizedQuery, ...]


def normalize_ingested(payload: IngestOutput) -> NormalizeOutput:
    if not payload.queries:
        raise CodegenDiagnosticError(
            "normalize",
            "Ingest output has no queries to normalize.",
            hint="Run the ingest stage with a directory containing query .scm files.",
        )

    normalized_queries = []
    ordered_queries = sorted(payload.queries, key=lambda query: query.provenance.file_path)
    for query in ordered_queries:
        patterns = _extract_patterns(query.source_text, query.provenance.file_path)
        if not patterns:
            raise CodegenDiagnosticError(
                "normalize",
                f"Query file {query.provenance.file_path} did not contain any parseable patterns.",
                hint="Ensure the file has non-comment, non-empty pattern lines.",
            )

        dedupe_check = {pattern.pattern_id for pattern in patterns}
        if len(dedupe_check) != len(patterns):
            raise CodegenDiagnosticError(
                "normalize",
                f"Duplicate pattern IDs were generated for {query.provenance.file_path}",
                hint="Check for repeated patterns or report this hash-collision bug.",
            )

        normalized_queries.append(NormalizedQuery(provenance=query.provenance, patterns=tuple(patterns)))

    return NormalizeOutput(queries=tuple(normalized_queries))


def _extract_patterns(source_text: str, file_path: str) -> list[NormalizedPattern]:
    cleaned_lines = [line.strip() for line in source_text.splitlines() if line.strip() and not line.strip().startswith(";")]
    patterns: list[NormalizedPattern] = []

    for ordinal, pattern_text in enumerate(cleaned_lines, start=1):
        capture_names = sorted(set(_CAPTURE_RE.findall(pattern_text)))
        captures = [
            NormalizedCapture(capture_id=f"cap_{sha1(name.encode('utf-8')).hexdigest()[:10]}", name=name)
            for name in capture_names
        ]
        pattern_hash_seed = f"{file_path}:{ordinal}:{pattern_text}"
        pattern_id = f"pat_{sha1(pattern_hash_seed.encode('utf-8')).hexdigest()[:12]}"
        patterns.append(
            NormalizedPattern(
                ordinal=ordinal,
                pattern_id=pattern_id,
                source=pattern_text,
                captures=tuple(captures),
            )
        )

    return patterns
