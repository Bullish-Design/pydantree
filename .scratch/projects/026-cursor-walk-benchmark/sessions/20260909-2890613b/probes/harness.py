"""Shared harness: grammars, corpora, and the three anchor strategies.

Session 20260909-2890613b. Independent re-derivation of Appendix E idea 10.

The harness holds no verdict. It builds the five language grammars, resolves
the real-file corpus, and exposes the three anchor-discovery strategies that
the oracle and the benchmark both consume.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import tree_sitter

REPO = Path(__file__).resolve().parents[6]
SESSION = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("PDT_BENCH_CACHE", "/tmp/pdt-bench-cache"))

# --------------------------------------------------------------------------
# corpus — real files only, pinned by absolute path and checked by sha256
# --------------------------------------------------------------------------

RUST_SRC = Path("/nix/store/qywrfqfkjzvkwfv1whndvkl7sy2wrxrf-rust-lib-src")
NIXPKGS = Path("/nix/store/77dbgds155bbz3vd3qywq1sii07i5ljs-source")
NIX_SCRIPTS = Path("/nix/store/4g5azly9lc7v75k1iazydm4rnbir0255-source")

CORPUS: dict[str, dict[str, Path]] = {
    "python": {
        "small": REPO / "src/pydantree_sitter/span.py",
        "medium": REPO / "src/pydantree_sitter/nodes.py",
        "large": REPO / ".venv/lib/python3.13/site-packages/mypy/checker.py",
    },
    "bash": {
        "small": REPO / "examples/bash-extract/sample.sh",
        "medium": NIX_SCRIPTS / "scripts/install-multi-user.sh",
        "large": REPO / ".devenv/shell-d5f9709ac96d0de3.sh",
    },
    "nix": {
        "small": REPO / "devenv.nix",
        "medium": REPO / "tests/fixtures/nix/fleet/flora.nix",
        "large": NIXPKGS / "pkgs/top-level/aliases.nix",
    },
    "rust": {
        "small": RUST_SRC / "core/src/mem/type_info.rs",
        "medium": RUST_SRC / "coretests/tests/num/mod.rs",
        "large": RUST_SRC / "alloc/src/sync.rs",
    },
    "markdown": {
        "small": REPO / "docs/typed-node-universe.md",
        "medium": REPO / "docs/development.md",
        "large": REPO / ".scratch/projects/024-typed-node-universe/REFACTOR_GUIDE.md",
    },
}


@dataclass(frozen=True)
class CorpusFile:
    language: str
    tier: str
    path: Path
    text: bytes
    sha256: str

    @property
    def bytes(self) -> int:
        return len(self.text)


def corpus_files() -> list[CorpusFile]:
    out = []
    for language, tiers in CORPUS.items():
        for tier, path in tiers.items():
            data = path.read_bytes()
            out.append(CorpusFile(language, tier, path, data,
                                  hashlib.sha256(data).hexdigest()))
    return out


# --------------------------------------------------------------------------
# grammars
# --------------------------------------------------------------------------

def _community_grammar(dir_name: str, name: str):
    """Build (or reuse) a community bundle and load it as a Grammar."""
    from pydantree_sitter import Grammar
    from pydantree_sitter_grammar.schema_tool import build_community_bundle

    out = CACHE / f"{dir_name}-bundle"
    if not (out / "node-schema.json").exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        build_community_bundle(REPO / "tests" / "fixtures" / dir_name, out,
                               name=name)
    return Grammar.load_bundle(out)


def _python_grammar():
    import tree_sitter_python

    from pydantree_sitter import Grammar
    from pydantree_sitter.schema import NodeSchema

    schema = NodeSchema.from_node_types_json(
        REPO / "examples/wheel-extract/vendor/python-node-types.json",
        name="python")
    return Grammar.load(tree_sitter.Language(tree_sitter_python.language()),
                        schema)


_GRAMMARS: dict[str, object] = {}


def grammar(language: str):
    if language not in _GRAMMARS:
        if language == "python":
            _GRAMMARS[language] = _python_grammar()
        elif language == "markdown":
            _GRAMMARS[language] = _community_grammar("markdown", "markdown")
        else:
            _GRAMMARS[language] = _community_grammar(language, language)
    return _GRAMMARS[language]


# --------------------------------------------------------------------------
# the three anchor-discovery strategies
# --------------------------------------------------------------------------

def anchors_query(raw, cls, language):
    """Strategy A — the shipped compiled-query anchor path (find._query_walk).

    Returns (anchors, fell_back) where fell_back records a QueryBuildError.
    """
    from pydantree_sitter.errors import QueryBuildError
    from pydantree_sitter.find import query_source
    from pydantree_sitter.match import match_ancestor_path
    from pydantree_sitter.nodes import normalize_under
    from pydantree_sitter.raw import Cursor, Query

    under = tuple(getattr(cls, "__under__", None) or ())
    path = normalize_under((*under, cls))
    query = Query.raw(query_source(cls))
    try:
        matches = Cursor(query.compile(language), raw).matches_on(raw)
    except QueryBuildError:
        return anchors_recwalk(raw, cls), True
    seen: set[tuple[int, int]] = set()
    out = []
    for match in matches:
        for anchor in match.nodes("__anchor"):
            key = (anchor.start_byte, anchor.end_byte)
            if key in seen or not match_ancestor_path(anchor, path):
                continue
            seen.add(key)
            out.append(anchor)
    return out, False


def anchors_recwalk(raw, cls):
    """Strategy B — the shipped recursive named_children fallback (find._walk)."""
    from pydantree_sitter.match import match_ancestor_path
    from pydantree_sitter.nodes import normalize_under

    under = tuple(getattr(cls, "__under__", None) or ())
    path = normalize_under((*under, cls))
    kind = cls.__kind__
    out = []

    def visit(candidate):
        if candidate.type == kind and match_ancestor_path(candidate, path):
            out.append(candidate)
        for child in candidate.named_children:
            visit(child)

    visit(raw)
    return out


def anchors_cursor(raw, cls, language):
    """Strategy C — the TreeCursor prototype (this investigation's candidate).

    One pre-order pass with a persistent cursor. No per-node child list is
    built, and the kind test is an integer compare on ``kind_id``.
    """
    from pydantree_sitter.match import match_ancestor_path
    from pydantree_sitter.nodes import normalize_under

    under = tuple(getattr(cls, "__under__", None) or ())
    path = normalize_under((*under, cls))
    kind_id = language.id_for_node_kind(cls.__kind__, True)
    out = []
    if kind_id is None:
        return out
    cursor = raw.walk()
    while True:
        node = cursor.node
        if node.kind_id == kind_id and node.is_named and \
                match_ancestor_path(node, path):
            out.append(node)
        if cursor.goto_first_child():
            continue
        if cursor.goto_next_sibling():
            continue
        while True:
            if not cursor.goto_parent():
                return out
            if cursor.goto_next_sibling():
                break


def rows_from(anchors, cls):
    """Resolve anchors into typed rows, mirroring find_in's per-match policy."""
    from pydantree_sitter.nodes import _MatchRejected

    rows, failures = [], []
    for anchor in anchors:
        try:
            rows.append(cls.from_node(anchor))
        except _MatchRejected:
            pass
        except Exception as error:  # noqa: BLE001 - per-match diagnostics
            failures.append((anchor.start_byte, anchor.end_byte, str(error)))
    return rows, failures


def find_in_cursor(raw, cls, language):
    """The prototype's ``find_in``: cursor anchors, unchanged resolver.

    It keeps the raw-query escape hatch and the ExtractionError contract.
    """
    from pydantree_sitter.errors import ExtractionError
    from pydantree_sitter.find import _Failure, _raw_find

    if getattr(cls, "__raw_query__", None) is not None:
        rows, failures = _raw_find(raw, cls, language)
        if failures:
            raise ExtractionError(failures, cls)
        return rows
    anchors = anchors_cursor(raw, cls, language)
    rows, raw_failures = rows_from(anchors, cls)
    if raw_failures:
        failures = [_Failure(0, None, "", detail)
                    for _s, _e, detail in raw_failures]
        raise ExtractionError(failures, cls)
    return rows
