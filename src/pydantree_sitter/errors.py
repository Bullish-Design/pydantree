"""pydantree_sitter.errors — the error taxonomy (014 refactor §1.3).

Wired in as the phases land: `BundleError` (loader, Phase 3); the A-side
extraction/coercion errors move here in Phase 4; the B-side grammar errors
live in `pydantree_sitter_grammar.errors` (Phase 6).

    PydantreeSitterError(Exception)
      BundleError       # loader: missing/invalid metadata, unknown format
"""


class PydantreeSitterError(Exception):
    """Base for all pydantree-sitter errors."""


class BundleError(PydantreeSitterError):
    """A bundle directory is missing/invalid metadata, or its
    `bundle_format` is unknown. Names both versions when rejecting a format,
    so a consumer can tell what it must upgrade to."""
