"""Grammar agreement — the §4 regression guard (022 §15).

Phase 0 measured that ast-grep's vendored Python grammar and
`tree_sitter_python` agree exactly, over `src/pydantree_sitter/`. That result
is committed in `agreement.AGREEMENT_RECORDS`, and the module's whole
handoff rule rests on it.

This file re-runs the measurement. A bump of `ast-grep-py`, a grammar wheel,
or `tree-sitter` that breaks agreement fails the suite HERE, with the numbers
attached, rather than surfacing later as a `PatternResolutionError` in a
consumer.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

pytest.importorskip("ast_grep_py")
tree_sitter_python = pytest.importorskip("tree_sitter_python")

from pydantree_sitter import Language
from pydantree_sitter.agreement import (
    AGREEMENT_RECORDS,
    agreement_for,
    char_to_byte_table,
    measure_agreement,
)
from pydantree_sitter.pattern import Edit, _apply

CORPUS = sorted((Path(__file__).resolve().parents[1]
                 / "src" / "pydantree_sitter").glob("*.py"))


@pytest.fixture(scope="module")
def lang():
    return Language.from_module(tree_sitter_python)


# -- offsets ----------------------------------------------------------------

def test_char_to_byte_table_covers_the_end_offset():
    """An exclusive end offset needs the entry AT len(text)."""
    table = char_to_byte_table("ab")
    assert table == [0, 1, 2]


def test_char_to_byte_table_on_multibyte_text():
    """The Phase 0 finding: ast-grep reports CHARACTER offsets and pydantree
    is byte offsets throughout."""
    text = 'x = "ééé"'
    table = char_to_byte_table(text)
    assert len(text) == 9 and len(text.encode("utf-8")) == 12
    assert table[len(text)] == 12
    assert table[5] == 5 and table[6] == 7      # each 'é' is two bytes


def test_the_corpus_actually_exercises_the_conversion():
    """A pure-ASCII corpus would make the agreement result meaningless: the
    naive and the correct conversion would agree everywhere."""
    assert any(not p.read_text(encoding="utf-8").isascii() for p in CORPUS)


# -- the guard --------------------------------------------------------------

def test_python_grammars_still_agree_exactly(lang):
    """The Phase 0 gate, as a test. Named AND anonymous nodes."""
    sources = [p.read_text(encoding="utf-8") for p in CORPUS]
    measured = measure_agreement(lang, "python", sources)
    assert measured.total_nodes > 20000, "the corpus shrank — check CORPUS"
    assert measured.exact_matches == measured.total_nodes, (
        f"ast-grep and tree_sitter_python disagree on "
        f"{measured.total_nodes - measured.exact_matches} node(s); "
        f"kinds: {measured.kind_mismatches[:10]}")
    assert measured.verified is True


def test_the_committed_record_matches_what_is_installed():
    """`verified` False here means the record describes a different world
    than the one running. Re-run the Phase 0 spike and update
    AGREEMENT_RECORDS."""
    record = agreement_for("python")
    assert record.verified, record.warnings


def test_the_committed_record_is_a_full_agreement(lang):
    """The committed counts are PROVENANCE of the Phase 0 run — the corpus is
    this package's own source, so it grows with the package and the counts
    are not an invariant. What IS an invariant is that the recorded run was a
    complete agreement, and that a fresh one still is (above)."""
    committed = AGREEMENT_RECORDS["python"]
    assert committed.rate == 1.0
    assert committed.kind_mismatches == ()
    assert committed.range_mismatches == ()


def test_the_digest_covers_every_dependency_version():
    """Two trajectories months apart are comparable only if the digest
    matches, so it must move when any measured version moves."""
    record = AGREEMENT_RECORDS["python"]
    for field in ("astgrep_version", "grammar_version", "tree_sitter_version"):
        drifted = record.model_copy(update={field: "0.0.0-test"})
        assert drifted.digest != record.digest, field


# -- the edit arithmetic, as a property -------------------------------------
#
# 022 §15 asks for a hypothesis property test, citing existing practice in
# `match.py`. There is no hypothesis in this repository and none in that
# file, so this generates its own cases from a fixed seed instead of adding a
# dependency: reproducible, and it fails with the exact case printed.

def _random_edits(rng, length):
    """A non-overlapping edit set over a buffer of `length` bytes."""
    edits = []
    cursor = 0
    while cursor < length:
        gap = rng.randint(0, 3)
        start = cursor + gap
        if start >= length:
            break
        end = min(start + rng.randint(1, 4), length)
        edits.append(Edit(start_byte=start, end_byte=end,
                          new_text="Z" * rng.randint(0, 5)))
        cursor = end
    return tuple(edits)


@pytest.mark.parametrize("seed", range(50))
def test_right_to_left_application_equals_a_left_to_right_reference(seed):
    """Right-to-left offset arithmetic is where this module would have its
    bug. The reference applies left to right and tracks the drift by hand."""
    rng = random.Random(seed)
    source = "".join(rng.choice("ab \né") for _ in range(rng.randint(1, 60)))
    data = source.encode("utf-8")
    edits = _random_edits(rng, len(data))
    # only split on character boundaries — a byte offset inside a multi-byte
    # character is not a legal edit boundary and never arises from a node
    edits = tuple(e for e in edits
                  if not _splits_a_character(data, e.start_byte)
                  and not _splits_a_character(data, e.end_byte))
    if not edits:
        pytest.skip("no legal edit boundaries in this case")

    reference = data
    drift = 0
    for edit in sorted(edits, key=lambda e: e.start_byte):
        new = edit.new_text.encode("utf-8")
        reference = (reference[:edit.start_byte + drift] + new
                     + reference[edit.end_byte + drift:])
        drift += len(new) - (edit.end_byte - edit.start_byte)

    assert _apply(source, edits) == reference.decode("utf-8"), \
        f"seed={seed} source={source!r} edits={edits}"


def _splits_a_character(data: bytes, offset: int) -> bool:
    return offset < len(data) and 0x80 <= data[offset] < 0xC0
