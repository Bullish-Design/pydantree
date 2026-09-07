"""The rewrite round-trip invariant, over this package's own source.

022 §15 states it as raw text equality:

    a replacement whose template equals the pattern must return
    `new_source == source`, for every corpus file

That is FALSE, and not because of a defect: an ast-grep template puts a
literal space where the source had a line break, so a `$$$BODY` covering an
indented block comes back collapsed. The `ast-grep` CLI collapses identically.

What holds is the invariant after a formatter pass. `ruff format` is a dev
dependency, so the check lives HERE and never in the module — the module is
language-generic and takes no formatter dependency.

Measured on the way in (`.scratch/projects/022-astgrep-pattern/`):

  * raw equality                     28 / 54 cases
  * after `ruff format`              35 / 54 cases
  * ...and the other 19 were BROKEN rewrites, not formatting noise. They are
    now refused by the edit-site check in `Pattern._verify_reparse`, so they
    never reach this test. Of the rewrites that survive, the formatted round
    trip is total.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytest.importorskip("ast_grep_py")
tree_sitter_python = pytest.importorskip("tree_sitter_python")

from pydantree_sitter import Language, Pattern
from pydantree_sitter.errors import PatternRewriteError

CORPUS = sorted((Path(__file__).resolve().parents[1]
                 / "src" / "pydantree_sitter").glob("*.py"))

TEMPLATES = [
    "def $NAME($$$ARGS): $$$BODY",
    "if $COND: $$$BODY",
    "for $VAR in $ITER: $$$BODY",
    "class $NAME($$$BASES): $$$BODY",
    "$A = $B",
    "return $VAL",
]


def ruff_format(text: str) -> str | None:
    """`text` formatted, or None when ruff refuses it."""
    proc = subprocess.run(
        ["ruff", "format", "--stdin-filename", "roundtrip.py", "-"],
        input=text, capture_output=True, text=True, check=False)
    return proc.stdout if proc.returncode == 0 else None


@pytest.fixture(scope="module")
def lang():
    return Language.from_module(tree_sitter_python)


@pytest.fixture(scope="module")
def ruff_available():
    if ruff_format("x = 1\n") is None:
        pytest.skip("ruff is not on PATH")
    return True


def test_identity_rewrites_round_trip_after_formatting(lang, ruff_available):
    """The invariant that survives: an identity template changes nothing a
    formatter can see.

    Counted, not just asserted — the numbers are the finding. A per-template
    assertion would be wrong here: the edit-site check refuses EVERY case for
    some templates (a `for` body over this corpus always leaks), and "no
    surviving case" is a legitimate outcome for one template but not for the
    corpus as a whole.
    """
    refused = checked = 0
    for path in CORPUS:
        source = path.read_text(encoding="utf-8")
        formatted_source = ruff_format(source)
        for template in TEMPLATES:
            pat = Pattern(template, language=lang)
            try:
                result = pat.replace_all(source, template)
            except PatternRewriteError:
                # nested matches (overlap), or an edit that would leak. Both
                # are refused by design, and neither is a round-trip question.
                refused += 1
                continue
            if result.count == 0:
                continue
            checked += 1
            formatted_result = ruff_format(result.new_source)
            assert formatted_result is not None, (
                f"{path.name} :: {template}: the rewrite produced source ruff "
                f"cannot parse, and the module accepted it — the edit-site "
                f"check has a hole")
            assert formatted_result == formatted_source, \
                f"{path.name} :: {template}"
    assert checked >= 30, f"only {checked} cases survived — the corpus moved"
    assert refused, "nothing was refused — the safety checks are not running"


def test_raw_round_trip_is_NOT_an_invariant(lang):
    """The counterpart, pinned so it cannot be quietly assumed later.

    022 §15 claims raw text equality. Over this corpus it holds for about
    four of five surviving rewrites, and the rest come back with a body
    collapsed onto its header line. That is ast-grep's template semantics —
    the CLI collapses identically — so the raw claim must stay false on
    purpose.
    """
    collapsed = 0
    for path in CORPUS:
        source = path.read_text(encoding="utf-8")
        for template in TEMPLATES:
            pat = Pattern(template, language=lang)
            try:
                result = pat.replace_all(source, template)
            except PatternRewriteError:
                continue
            if result.count and result.new_source != source:
                collapsed += 1
    assert collapsed, (
        "every identity rewrite came back byte-identical — if ast-grep "
        "changed its template semantics, 022 §15's raw invariant may now be "
        "true and this file should be simplified")


def test_every_surviving_rewrite_is_valid_python(lang):
    """The stronger claim, without a formatter: anything `replace_all`
    returns must parse with CPython itself.

    tree-sitter's `has_error` is NOT sufficient for this — it accepts source
    CPython rejects — which is why `_verify_reparse` also checks that each
    edit occupies exactly one node.
    """
    import ast
    checked = 0
    for path in CORPUS:
        source = path.read_text(encoding="utf-8")
        for template in TEMPLATES:
            pat = Pattern(template, language=lang)
            try:
                result = pat.replace_all(source, template)
            except PatternRewriteError:
                continue
            if result.count == 0:
                continue
            checked += 1
            try:
                ast.parse(result.new_source)
            except SyntaxError as exc:
                pytest.fail(f"{path.name} :: {template} produced invalid "
                            f"Python that the module accepted: {exc}")
    assert checked
