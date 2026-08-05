"""The community node-type fixtures — one immutable shared manifest.

Single source of truth for the retained community grammar fixtures that the
repository treats as real oracles (V5/V6): `tests/fixtures/{bash,rust,nix,
markdown,markdown-inline}/node-types.json` must regenerate byte-for-byte
with the installed, supported tree-sitter CLI (0.25.x, pinned 0.25.3 in this
repository).

Both `tests/regenerate_community_node_types.py` (the explicit refresh
command) and `tests/test_community_fixtures.py` (the drift guard) consume
this manifest, so the two can never drift into separate hand-maintained
lists.

The `jsonlike*` node-type files under `tests/fixtures/` are NOT here: they
are in-project schema-consumption fixtures (serialized-form round-trips),
not upstream community byproducts. This manifest covers only the five
retained upstream fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommunityFixture:
    """One vendored community grammar source dir + its expected byproduct."""

    dir_name: str                 # directory under tests/fixtures/
    grammar_name: str             # grammar/export name (the tree-sitter name)
    upstream_repo: str            # upstream repository URL
    tag: str | None               # upstream tag the source was vendored from
    commit: str                   # full 40-char upstream commit
    commit_date: str              # upstream commit date (YYYY-MM-DD)
    commit_title: str             # upstream commit subject
    byproduct_path: str           # expected byproduct, relative to the dir
    license: str                  # upstream license
    acquired: str                 # when this repository vendored the source
    # The exact upstream source files whose bytes are vendored:
    source_files: tuple[str, ...]


COMMUNITY_FIXTURES: tuple[CommunityFixture, ...] = (
    CommunityFixture(
        dir_name="bash",
        grammar_name="bash",
        upstream_repo="https://github.com/tree-sitter/tree-sitter-bash",
        tag="v0.25.1",
        commit="a06c2e4415e9bc0346c6b86d401879ffb44058f7",
        commit_date="2025-12-02",
        commit_title="Regenerate parser for 0.25.1",
        byproduct_path="node-types.json",
        license="MIT",
        acquired="2026-08-04",
        source_files=(
            "src/grammar.json",
            "src/scanner.c",
            "src/tree_sitter/alloc.h",
            "src/tree_sitter/array.h",
            "src/tree_sitter/parser.h",
        ),
    ),
    CommunityFixture(
        dir_name="rust",
        grammar_name="rust",
        upstream_repo="https://github.com/tree-sitter/tree-sitter-rust",
        tag=None,
        commit="b3e615de069beb04ff44f65ac52f7f03cff04438",
        commit_date="2026-03-27",
        commit_title="Fix bad error recovery when parsing repeated string literals (#307)",
        byproduct_path="node-types.json",
        license="MIT",
        acquired="2026-08-02",
        source_files=(
            "src/grammar.json",
            "src/scanner.c",
            "src/tree_sitter/alloc.h",
            "src/tree_sitter/array.h",
            "src/tree_sitter/parser.h",
        ),
    ),
    CommunityFixture(
        dir_name="nix",
        grammar_name="nix",
        upstream_repo="https://github.com/nix-community/tree-sitter-nix",
        tag="v0.3.0",
        commit="ea1d87f7996be1329ef6555dcacfa63a69bd55c6",
        commit_date="2025-07-18",
        commit_title="Release v0.3.0 (#147)",
        byproduct_path="node-types.json",
        license="MIT",
        acquired="2026-08-04",
        source_files=(
            "src/grammar.json",
            "src/scanner.c",
            "src/tree_sitter/parser.h",
        ),
    ),
    CommunityFixture(
        dir_name="markdown",
        grammar_name="markdown",
        upstream_repo="https://github.com/tree-sitter-grammars/tree-sitter-markdown",
        tag=None,
        commit="808e105aff82bc7cbc1587384dab71151b62182f",
        commit_date="2026-02-26",
        commit_title="chore: regenerate parser and bindings with 0.26.6",
        byproduct_path="node-types.json",
        license="MIT",
        acquired="2026-08-03",
        source_files=(
            "tree-sitter-markdown/src/grammar.json",
            "tree-sitter-markdown/src/scanner.c",
            "tree-sitter-markdown/src/tree_sitter/alloc.h",
            "tree-sitter-markdown/src/tree_sitter/array.h",
            "tree-sitter-markdown/src/tree_sitter/parser.h",
        ),
    ),
    CommunityFixture(
        dir_name="markdown-inline",
        grammar_name="markdown_inline",
        upstream_repo="https://github.com/tree-sitter-grammars/tree-sitter-markdown",
        tag=None,
        commit="808e105aff82bc7cbc1587384dab71151b62182f",
        commit_date="2026-02-26",
        commit_title="chore: regenerate parser and bindings with 0.26.6",
        byproduct_path="node-types.json",
        license="MIT",
        acquired="2026-08-03",
        source_files=(
            "tree-sitter-markdown-inline/src/grammar.json",
            "tree-sitter-markdown-inline/src/scanner.c",
            "tree-sitter-markdown-inline/src/tree_sitter/alloc.h",
            "tree-sitter-markdown-inline/src/tree_sitter/array.h",
            "tree-sitter-markdown-inline/src/tree_sitter/parser.h",
        ),
    ),
)

FIXTURES_DIR = "tests/fixtures"

# CLI ranges the byte-for-byte claim is verified against (see
# tests/conftest.py CLI_VERIFIED / REVIEW 018 §1.4/B7). Kept in the
# manifest so the regeneration command and the drift guard share the same
# supported-range statement.
SUPPORTED_CLI = "0.25.x (pinned 0.25.3 in this repository)"
