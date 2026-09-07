"""A pydantree-BUILT grammar, driven by ast-grep (022 §7, corrected).

CONCEPT §7 states that ast-grep "supports a fixed set of languages, compiled
into its wheel" and that "a custom grammar built by pydantree-sitter-grammar
has no ast-grep support". The second half is false:
`ast_grep_py.register_dynamic_language` accepts any tree-sitter shared
library, and `pydantree_sitter_grammar` writes exactly one per bundle.

The load-bearing test is `test_the_two_engines_parse_identically`. It is the
whole reason this matters: with one artifact on both sides, §4's divergence
risk does not exist. Not "was measured and found small" — does not exist.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("ast_grep_py")

pytestmark = [pytest.mark.toolchain, pytest.mark.slow]

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "grammars"
if str(FIXTURES) not in sys.path:
    sys.path.insert(0, str(FIXTURES))

from pydantree_sitter import Language, Pattern, Rule
from pydantree_sitter.errors import BundleError, PatternBuildError
from pydantree_sitter.pattern import (
    register_bundle_language,
    registered_languages,
)

SRC = '{"host": "x", "port": 1}'


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    """A real bundle: grammar.so + node-schema.json + metadata."""
    from json_grammar import build

    import pydantree_sitter_grammar as tg
    from pydantree_sitter_grammar.pipeline import write_bundle
    out = tmp_path_factory.mktemp("dynbundle") / "bundle"
    return Path(str(write_bundle(tg.build(build().build()), out)))


@pytest.fixture(scope="module")
def dyn_lang(bundle):
    lang = Language.load_bundle(bundle)
    lang.register_astgrep("pydantree_json_test")
    return lang


# -- the artifact -----------------------------------------------------------

def test_the_bundle_exports_the_symbol_astgrep_needs(bundle):
    """ast-grep dlopens the .so and looks up `tree_sitter_<name>`. If the
    bundle ever stops exporting it, registration fails at a distance."""
    out = subprocess.run(["nm", "-D", "--defined-only", str(bundle / "grammar.so")],
                         capture_output=True, text=True, check=False)
    assert "tree_sitter_json" in out.stdout


def test_registering_sets_the_astgrep_name(dyn_lang):
    assert dyn_lang.astgrep_is_bundle is True
    assert dyn_lang.astgrep_name == "pydantree_json_test"
    assert "pydantree_json_test" in registered_languages()


def test_a_wheel_language_cannot_be_registered():
    """ast-grep needs a file to dlopen, and a wheel's Language has none."""
    tree_sitter_python = pytest.importorskip("tree_sitter_python")
    lang = Language.from_module(tree_sitter_python)
    assert lang.astgrep_is_bundle is False
    with pytest.raises(BundleError) as exc:
        lang.register_astgrep("nope")
    assert "load_bundle" in str(exc.value)


def test_reregistering_a_name_with_another_artifact_is_refused(dyn_lang, bundle):
    """Registration is PROCESS-GLOBAL — ast-grep's design, not something this
    module can scope. Silently rebinding a name would change what every
    Pattern already built on it parses."""
    with pytest.raises(PatternBuildError) as exc:
        register_bundle_language("pydantree_json_test", "/somewhere/else.so",
                                 "tree_sitter_json")
    assert "already registered" in str(exc.value)
    assert "process-global" in str(exc.value)


def test_reregistering_the_same_artifact_is_a_no_op(dyn_lang, bundle):
    assert dyn_lang.register_astgrep("pydantree_json_test") == "pydantree_json_test"


# -- the point --------------------------------------------------------------

def test_the_two_engines_parse_identically(dyn_lang):
    """One `.so`, both engines, identical node sets.

    This is what makes a bundle the BEST-supported case rather than the
    unsupported one. §4's handoff rule still runs — ast-grep finds,
    pydantree resolves — but it can no longer fail, because there is nothing
    for the two grammars to disagree about.
    """
    from ast_grep_py import SgRoot

    ours = []
    stack = [dyn_lang.parse(SRC.encode()).root_node]
    while stack:
        n = stack.pop()
        ours.append((n.type, n.start_byte, n.end_byte))
        stack.extend(n.children)

    theirs = []
    stack = [SgRoot(SRC, dyn_lang.astgrep_name).root()]
    while stack:
        n = stack.pop()
        r = n.range()
        theirs.append((n.kind(), r.start.index, r.end.index))
        stack.extend(n.children())

    assert len(ours) > 10
    assert sorted(ours) == sorted(theirs)


def test_agreement_is_by_construction_not_measurement(dyn_lang):
    pat = Pattern(Rule(kind="pair"), language=dyn_lang)
    assert pat.agreement.verified is True
    assert pat.agreement.same_artifact is True
    assert pat.warnings == ()          # nothing to warn about


def test_search_over_an_authored_grammar(dyn_lang):
    pat = Pattern(Rule(kind="pair"), language=dyn_lang)
    matches = pat.find_all(SRC)
    assert [m.text for m in matches] == ['"host": "x"', '"port": 1']
    assert all(m.node.type == "pair" for m in matches)


def test_the_schema_check_uses_the_bundle_schema(dyn_lang):
    """The bundle carries node-schema.json, so an unknown kind is rejected by
    name at construction — the highest-value check, now available for an
    authored grammar too."""
    with pytest.raises(PatternBuildError) as exc:
        Pattern(Rule(kind="paiir"), language=dyn_lang)
    assert "'paiir'" in str(exc.value)


def test_rewrite_over_an_authored_grammar_still_validates(dyn_lang):
    """No `syntax_check` is registered for this language, so the structural
    proxy is the AUTO default — which is exactly where that fallback
    belongs."""
    result = dyn_lang.syntax_check
    assert result is None
    pat = Pattern(Rule(kind="pair"), language=dyn_lang)
    ok = pat.replace_all(SRC, '"replaced": 0')
    assert ok.new_source == '{"replaced": 0, "replaced": 0}'
    assert ok.diagnostics == ()


def test_a_metavariable_sigil_the_grammar_cannot_lex_finds_nothing(dyn_lang):
    """A documented trap, pinned. `$` is not a JSON token, so a `$H` pattern
    does not parse as JSON and matches NOTHING — silently. `meta_var_char`
    exists for this, and a grammar with free-form text (markdown) is fine
    with the default.
    """
    pat = Pattern('{"host": $H}', language=dyn_lang)
    assert pat.find_all(SRC) == ()
    # ...while the rule form, which needs no pattern parse, works
    assert Pattern(Rule(kind="pair"), language=dyn_lang).find_all(SRC)
