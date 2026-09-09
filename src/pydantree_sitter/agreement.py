"""pydantree_sitter.agreement — the two-parser boundary (022 §4).

`ast-grep-py` vendors its own tree-sitter grammars. For a wheel grammar,
pydantree parses with `tree_sitter_python` and records the measured agreement
between two grammar revisions. For a registered bundle, both sides load the
same shared library, so the agreement is established by construction.

This module owns everything that crosses between them:

  * `char_to_byte_table` — ast-grep reports CHARACTER offsets; pydantree is
    byte offsets throughout. The conversion is mandatory, not a nicety.
  * `GrammarAgreement` — the recorded evidence that the two grammars agree,
    plus the bind-time version check against it.
  * `measure_agreement` — the explicit regeneration and evidence helper for
    wheel-grammar records.

The handoff rule (§4.1) is enforced in `pattern.py`, and it depends on this
module's offsets being right:

    ast-grep finds. pydantree resolves. Disagreement is an error, never a guess.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

import tree_sitter
from pydantic import BaseModel, ConfigDict

__all__ = [
    "AGREEMENT_RECORDS",
    "GrammarAgreement",
    "agreement_for",
    "char_to_byte_table",
    "dist_version",
    "measure_agreement",
]


# ---------------------------------------------------------------------------
# offsets — the finding that decided the implementation (022 Phase 0)
# ---------------------------------------------------------------------------

def char_to_byte_table(text: str) -> list[int]:
    """Map every character index in `text` to its UTF-8 byte offset.

    `ast_grep_py` reports positions as `Range(start=Pos, end=Pos)` and
    `Pos.index` is a **character** offset, NOT a byte offset. Every offset in
    pydantree is a byte offset. Without this conversion the two only agree on
    pure-ASCII source, and the Phase 0 corpus run proves the size of the gap:
    treating the character offsets as byte offsets drops node agreement over
    `src/pydantree_sitter/` from 100 % to 0.54 %.

    The table has `len(text) + 1` entries; the last one is the end of the
    buffer, which is what an exclusive end offset needs.

    Cost is O(len(text)). Build it ONCE per parse and keep it beside the
    tree — never per match.
    """
    table = [0] * (len(text) + 1)
    byte = 0
    for i, ch in enumerate(text):
        table[i] = byte
        byte += len(ch.encode("utf-8"))
    table[len(text)] = byte
    return table


def dist_version(name: str) -> str:
    """The installed distribution version, or `"unknown"`.

    Neither `ast_grep_py` nor `tree_sitter_python` exposes `__version__`, so
    read the metadata. This string goes into the agreement digest, and a
    literal `"unknown"` there makes two recorded runs incomparable — which is
    exactly what the digest exists to prevent.
    """
    try:
        return _dist_version(name)
    except PackageNotFoundError:  # pragma: no cover - depends on install shape
        return "unknown"


# ---------------------------------------------------------------------------
# the record
# ---------------------------------------------------------------------------

class GrammarAgreement(BaseModel):
    """Evidence that ast-grep's grammar and pydantree's agree — as data.

    This is a RECORDED artifact, not a per-bind measurement. CONCEPT.md §4.2
    proposed probing one fixture at every `Pattern` construction; Phase 0
    showed that a single fixture cannot demonstrate what a corpus run
    demonstrates, so shipping one would imply a guarantee it does not
    provide. Instead: the corpus run is committed here, and bind time checks
    that the INSTALLED dependency versions are the ones that were measured.

    `verified` is the whole point. True means "these exact versions were
    measured, and they agreed". False means "nothing here was measured for
    what you are running" — the numbers then describe a different world and
    `warnings` says so.
    """

    model_config = ConfigDict(frozen=True)

    language: str                      # the ast-grep language name
    astgrep_version: str               # ast-grep-py distribution version
    grammar_dist: str                  # e.g. "tree-sitter-python"
    grammar_version: str
    tree_sitter_version: str

    corpus_files: int = 0
    corpus_lines: int = 0
    total_nodes: int = 0               # named + anonymous, pydantree's count
    exact_matches: int = 0
    kind_mismatches: tuple[str, ...] = ()
    range_mismatches: tuple[tuple[int, int], ...] = ()

    verified: bool = False
    # True when ast-grep and pydantree load the SAME shared library — a
    # bundle registered with `register_bundle_language`. Then there is one
    # grammar, one revision, one artifact, and §4's divergence risk does not
    # exist rather than being measured away.
    same_artifact: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def rate(self) -> float | None:
        """The exact-agreement rate, or None when nothing was measured."""
        if not self.total_nodes:
            return None
        return self.exact_matches / self.total_nodes

    @property
    def digest(self) -> str:
        """A stable hash of the whole record.

        Every `PatternMatch` and `ReplaceResult` carries it (§17.10). Two
        trajectories recorded months apart are comparable only if this value
        matches, because it covers the ast-grep version AND both grammar
        revisions.
        """
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


# The committed Phase 0 result. Regenerate with
# `.scratch/projects/022-astgrep-pattern/spike_agreement.py` after any bump of
# ast-grep-py or a grammar wheel, and update `tests/test_pattern_agreement.py`
# — that test re-runs the measurement and fails the suite when a bump breaks
# it. This is the §4 regression guard.
AGREEMENT_RECORDS: dict[str, GrammarAgreement] = {
    "python": GrammarAgreement(
        language="python",
        astgrep_version="0.45.3",
        grammar_dist="tree-sitter-python",
        grammar_version="0.25.0",
        tree_sitter_version="0.26.0",
        # The Phase 0 evidence, describing the run that produced it: the
        # 16 files of src/pydantree_sitter/, every node compared, anonymous
        # included. These counts are PROVENANCE, not an invariant — the
        # corpus is this package's own source and it grows. The invariant is
        # `exact_matches == total_nodes`, and
        # tests/test_pattern_agreement.py re-measures it.
        corpus_files=16,
        corpus_lines=5131,
        total_nodes=39190,
        exact_matches=39190,
        verified=True,
    ),
}

# The grammar distribution each ast-grep language is measured against. A
# language absent here can still be used; it simply has no record, and the
# bind warning says so.
_GRAMMAR_DIST = {"python": "tree-sitter-python"}


def agreement_for(astgrep_name: str) -> GrammarAgreement:
    """The agreement record for `astgrep_name`, checked against what is
    actually installed.

    Never raises. An unrecorded language, or a version that drifted from the
    measured one, produces a record with `verified=False` and a warning —
    `Pattern` surfaces those warnings as data, once, and never prints them
    (the repository's warnings-are-data rule).
    """
    installed_astgrep = dist_version("ast-grep-py")
    installed_ts = tree_sitter.__version__
    dist = _GRAMMAR_DIST.get(astgrep_name)
    installed_grammar = dist_version(dist) if dist else "unknown"

    record = AGREEMENT_RECORDS.get(astgrep_name)
    if record is None:
        return GrammarAgreement(
            language=astgrep_name,
            astgrep_version=installed_astgrep,
            grammar_dist=dist or "unknown",
            grammar_version=installed_grammar,
            tree_sitter_version=installed_ts,
            verified=False,
            warnings=((
                f"no grammar-agreement record for {astgrep_name!r}: ast-grep "
                f"and pydantree may disagree on node kinds or byte ranges, "
                f"and that has never been measured here. A disagreement "
                f"raises PatternResolutionError rather than returning a wrong "
                f"node, so this is a coverage gap and not a correctness risk."
            ),),
        )

    drift = []
    if installed_astgrep != record.astgrep_version:
        drift.append(f"ast-grep-py {installed_astgrep} "
                     f"(measured {record.astgrep_version})")
    if dist and installed_grammar != record.grammar_version:
        drift.append(f"{dist} {installed_grammar} "
                     f"(measured {record.grammar_version})")
    if installed_ts != record.tree_sitter_version:
        drift.append(f"tree-sitter {installed_ts} "
                     f"(measured {record.tree_sitter_version})")
    if not drift:
        return record
    return record.model_copy(update={
        "verified": False,
        "astgrep_version": installed_astgrep,
        "grammar_version": installed_grammar,
        "tree_sitter_version": installed_ts,
        "warnings": (
            "grammar-agreement record does not match what is installed: "
            + "; ".join(drift)
            + ". Re-run the Phase 0 spike and update AGREEMENT_RECORDS.",
        ),
    })


# ---------------------------------------------------------------------------
# the measurement
# ---------------------------------------------------------------------------

def _ts_nodes(tree: tree_sitter.Tree) -> set[tuple[str, int, int]]:
    out: set[tuple[str, int, int]] = set()
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        out.add((node.type, node.start_byte, node.end_byte))
        stack.extend(node.children)
    return out


def _sg_nodes(root, table: list[int]) -> set[tuple[str, int, int]]:
    out: set[tuple[str, int, int]] = set()
    stack = [root]
    while stack:
        node = stack.pop()
        rng = node.range()
        out.add((node.kind(), table[rng.start.index], table[rng.end.index]))
        stack.extend(node.children())
    return out


def measure_agreement(language, astgrep_name: str, sources) -> GrammarAgreement:
    """Measure agreement over `sources` and return a fresh record.

    `sources` is an iterable of `str`. Every node is compared, anonymous
    nodes included: an anonymous-node boundary shift moves its named parent's
    range too, so excluding them would hide the divergence that matters.

    This is the regeneration path AND the regression test. It needs
    `ast_grep_py`, imported here rather than at module import so the base
    runtime stays free of the optional extra.
    """
    try:
        from ast_grep_py import SgRoot
    except ImportError as exc:  # pragma: no cover - exercised by the extra
        from .errors import PatternError
        raise PatternError(
            "measuring grammar agreement needs the `pattern` extra: "
            "pip install 'pydantree-sitter[pattern]'") from exc

    files = lines = total = exact = 0
    kinds: Counter[str] = Counter()
    ranges: list[tuple[int, int]] = []

    for text in sources:
        files += 1
        lines += text.count("\n")
        table = char_to_byte_table(text)
        ours = _ts_nodes(language.parse(text))
        theirs = _sg_nodes(SgRoot(text, astgrep_name).root(), table)
        total += len(ours)
        exact += len(ours & theirs)
        for kind, start, end in ours ^ theirs:
            kinds[kind] += 1
            if len(ranges) < 50:
                ranges.append((start, end))

    dist = _GRAMMAR_DIST.get(astgrep_name)
    return GrammarAgreement(
        language=astgrep_name,
        astgrep_version=dist_version("ast-grep-py"),
        grammar_dist=dist or "unknown",
        grammar_version=dist_version(dist) if dist else "unknown",
        tree_sitter_version=tree_sitter.__version__,
        corpus_files=files,
        corpus_lines=lines,
        total_nodes=total,
        exact_matches=exact,
        kind_mismatches=tuple(sorted(kinds)),
        range_mismatches=tuple(ranges),
        verified=(total > 0 and exact == total),
    )
