"""pydantree_sitter.errors — the error taxonomy (014 refactor §1.3).

    PydantreeSitterError(Exception)
      SchemaCheckError        # model↔grammar mismatch at bind time
      ShapeError              # unmappable value shape (class-creation or bind)
      QueryBuildError         # tree-sitter rejected the emitted/raw query
      ExtractionError         # per-match failures (strict mode), carries MatchFailure list
      AmbiguousCaptureError   # scalar field fed by multiple captures
      BundleError             # loader: missing/invalid metadata, unknown format

`SchemaCheckError` is a sibling of coercion failures, not a subclass (the old
`SchemaCheckError < CoercionError < ValueError` smell is gone — coercion
failures surface as pydantic ValidationErrors wrapped in `ExtractionError`).
"""


class PydantreeSitterError(Exception):
    """Base for all pydantree-sitter errors."""


class SchemaCheckError(PydantreeSitterError):
    """A model↔grammar or capture↔type check failed against the node-schema
    at bind time. Carries the schema entry (node kind, field, supertype)
    that the model conflicts with."""

    def __init__(self, message: str, *, schema_entry: str | None = None,
                 model: type | None = None):
        self.schema_entry = schema_entry
        self.model = model
        super().__init__(message)


class ShapeError(PydantreeSitterError):
    """A field's value shape cannot be mapped in the bound grammar (or the
    declaration itself is unmappable): use Annotated[..., NodeKind(...)] or
    run `propose_value_map(schema)` and pass the reviewed result."""


class QueryBuildError(PydantreeSitterError):
    """The emitted (or raw) .scm was rejected by tree_sitter.Query()."""


class AmbiguousCaptureError(PydantreeSitterError):
    """A scalar field was fed by multiple captures (nested key collision)."""


def raise_ambiguous_capture(fname: str, capture_name: str, count: int) -> None:
    """THE one AmbiguousCaptureError raise (A7): the message must not drift
    between the matcher's merge path and the materializer's build path."""
    raise AmbiguousCaptureError(
        f"field {fname!r} is scalar but capture "
        f"{capture_name!r} matched {count} nodes "
        f"(nested key collision?)")


class ExtractionError(PydantreeSitterError):
    """One or more matches failed to materialize (strict mode); `.failures`
    carries per-match detail (pattern index, anchor span, snippet, pydantic
    errors) instead of only the first error."""

    def __init__(self, failures: list, into):
        self.failures = failures
        self.into = into
        lines = [
            f"{len(failures)} match(es) failed to materialize "
            f"{into.__name__}:"]
        for f in failures:
            where = f"line {f.span.line}" if f.span is not None else "?"
            lines.append(
                f"  - pattern {f.pattern} @ {where} {f.snippet!r}: {f.detail}")
        super().__init__("\n".join(lines))


class BundleError(PydantreeSitterError):
    """A bundle directory is missing/invalid metadata, or its
    `bundle_format` is unknown. Names both versions when rejecting a format,
    so a consumer can tell what it must upgrade to."""
