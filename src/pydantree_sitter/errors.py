"""pydantree_sitter.errors — the error taxonomy (014 refactor §1.3).

    PydantreeSitterError(Exception)
    SchemaCheckError        # model↔grammar mismatch at bind time
      SchemaDistributionError # schema file is missing or malformed
        SchemaMissingError    # distribution data was not installed
        SchemaDataError       # installed data is not a node-types schema
      ShapeError              # unmappable value shape (class-creation or bind)
      QueryBuildError         # tree-sitter rejected a raw query
      ExtractionError         # per-match failures (strict mode), carries MatchFailure list
      BundleError             # loader: missing/invalid metadata, unknown format
      PatternError            # the pattern module (022 §9)
        PatternBuildError       # a rule failed validation / ast-grep rejected it
        PatternResolutionError  # a byte range did not resolve exactly (§4.1)
        PatternRewriteError     # overlapping edits, or a broken re-parse
        UnsupportedLanguageError# no ast-grep grammar for this Language

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


class SchemaDriftError(PydantreeSitterError):
    """A generated node universe does not match its loaded language."""


class SchemaDistributionError(PydantreeSitterError):
    """A schema distribution artifact cannot be loaded."""


class SchemaMissingError(SchemaDistributionError):
    """The application-owned schema file is not present."""


class SchemaDataError(SchemaDistributionError):
    """The installed schema file is present but malformed or invalid."""


class ShapeError(PydantreeSitterError):
    """A field annotation cannot be mapped to the loaded node schema."""


class QueryBuildError(PydantreeSitterError):
    """A raw .scm query was rejected by tree_sitter.Query()."""


class ExtractionError(PydantreeSitterError):
    """One or more matches failed to materialize (strict mode); `.failures`
    carries per-match detail (pattern index, anchor span, snippet, pydantic
    errors) instead of only the first error."""

    def __init__(self, failures: list, into):
        self.failures = failures
        self.into = into
        lines = [(
            f"{len(failures)} match(es) failed to materialize "
            f"{into.__name__}:")]
        for f in failures:
            where = f"line {f.span.line}" if f.span is not None else "?"
            lines.append(
                f"  - pattern {f.pattern} @ {where} {f.snippet!r}: {f.detail}")
        super().__init__("\n".join(lines))


class BundleError(PydantreeSitterError):
    """A bundle directory is missing/invalid metadata, or its
    `bundle_format` is unknown. Names both versions when rejecting a format,
    so a consumer can tell what it must upgrade to."""


# ---------------------------------------------------------------------------
# the pattern module (022 §9)
# ---------------------------------------------------------------------------

class PatternError(PydantreeSitterError):
    """Base for `pydantree_sitter.pattern` failures.

    It also carries the missing-dependency case: `ast-grep-py` is an optional
    extra, so `Pattern(...)` raises this when the engine is absent. That is
    deliberate — construction is where ALL of a Pattern's checks run (022
    §17.4), and "the extra is not installed" is one of them.
    """


class PatternBuildError(PatternError):
    """A rule failed validation, or ast-grep rejected the pattern.

    Raised by `Rule` validators without a grammar (empty rule, bad regex,
    over a bound) and by `Pattern.__init__` with one (unknown node kind,
    unparseable pattern).
    """


class PatternResolutionError(PatternError):
    """An ast-grep byte range did not resolve to an EXACT node in
    pydantree's own tree (022 §4.1).

    ast-grep finds. pydantree resolves. Disagreement is an error, never a
    guess: there is no fallback to the smallest enclosing node, because a
    plausible neighbouring node makes an extraction succeed with a wrong
    row, and that is the one failure mode this project exists to prevent.

    Carries the byte range, the pattern, the nearest node kind, and the
    grammar-agreement digest — enough to reproduce the divergence without
    the original session.
    """

    def __init__(self, message: str, *, start_byte: int, end_byte: int,
                 pattern: str | None = None, nearest_kind: str | None = None,
                 agreement: str | None = None):
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.pattern = pattern
        self.nearest_kind = nearest_kind
        self.agreement = agreement
        detail = [f"bytes {start_byte}..{end_byte}"]
        if pattern is not None:
            detail.append(f"pattern {pattern!r}")
        if nearest_kind is not None:
            detail.append(f"nearest node kind {nearest_kind!r}")
        if agreement is not None:
            detail.append(f"agreement {agreement}")
        super().__init__(f"{message} ({', '.join(detail)})")


class PatternRewriteError(PatternError):
    """A rewrite was refused: the edits overlap, or applying them breaks the
    parse (022 §8, §8.1).

    Overlap means the pattern matched nested occurrences. The correct
    behaviour is to refuse, not to pick one.
    """


class UnsupportedLanguageError(PatternError):
    """The bound `Language` has no ast-grep grammar.

    ast-grep compiles a fixed language set into its wheel; pydantree builds
    any grammar. A grammar from `pydantree-sitter-grammar` is simply outside
    that set, and the message says so plainly rather than implying a missing
    install.
    """
