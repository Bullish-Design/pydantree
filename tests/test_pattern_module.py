"""`pydantree_sitter.pattern` — structural search and rewrite (022 §3-§10).

The load-bearing tests are the ones about the two-parser handoff (§4.1) and
about edit safety (§8), because those are the two places where this module
can be SILENTLY wrong rather than loudly broken.
"""

from __future__ import annotations

import pytest

tree_sitter_python = pytest.importorskip("tree_sitter_python")
pytest.importorskip("ast_grep_py")

from pydantree_sitter import (
    Language,
    M,
    OutputModel,
    Pattern,
    Rule,
    Span,
    capture,
)
from pydantree_sitter.errors import (
    PatternBuildError,
    PatternError,
    PatternResolutionError,
    PatternRewriteError,
    UnsupportedLanguageError,
)
from pydantree_sitter.pattern import Edit, _apply, _reject_overlap

SOURCE = '''class A:
    def greet(self, name):
        return "h\u00e9llo " + name

def free(x, y=2):
    return x
'''


@pytest.fixture
def lang():
    return Language.from_module(tree_sitter_python)


@pytest.fixture
def defs(lang):
    return Pattern("def $NAME($$$ARGS): $$$BODY", language=lang)


# -- bind (§17.4: a built Pattern works or it raised) -----------------------

def test_language_resolves_its_astgrep_name(lang):
    assert lang.astgrep_name == "python"


def test_unsupported_language_names_the_reason_and_the_set(lang):
    """A custom grammar has no ast-grep counterpart, and the message must not
    imply a missing install (§7)."""
    tree_sitter_json = pytest.importorskip("tree_sitter_json")
    other = Language.from_module(tree_sitter_json)
    assert other.astgrep_name is None
    with pytest.raises(UnsupportedLanguageError) as exc:
        Pattern("$A", language=other)
    message = str(exc.value)
    assert "fixed language set" in message
    assert "not a missing install" in message
    assert "astgrep_name=" in message


def test_explicit_astgrep_name_overrides(lang):
    tree_sitter_json = pytest.importorskip("tree_sitter_json")
    other = Language.from_module(tree_sitter_json, astgrep_name="json")
    assert other.astgrep_name == "json"


def test_a_rule_ast_grep_rejects_fails_at_construction(lang):
    """Not on the first search — all checks run at bind (§17.4).

    An unknown `kind` is caught earlier, by the node-schema check, so this
    uses a regex ast-grep itself refuses. Note what is NOT checkable here:
    ast-grep parses a malformed PATTERN string leniently (`"def $NAME("` is
    accepted and simply matches nothing), so a nonsense pattern cannot be
    rejected at bind. Only rules can.
    """
    with pytest.raises(PatternBuildError):
        Pattern(Rule.model_construct(regex="(("), language=lang)


def test_a_rust_panic_stays_inside_the_taxonomy(lang):
    """`ast_grep_py` is a Rust extension and does not confine itself to
    `Exception`: an unsupported language aborts with a pyo3
    `PanicException`, which inherits from **BaseException**. `except
    Exception` does not see it, so it would escape the taxonomy and the
    caller's error handling entirely.
    """
    unsupported = Language.from_module(tree_sitter_python,
                                       astgrep_name="toml")
    with pytest.raises(PatternError) as exc:
        Pattern("$A = $B", language=unsupported)
    assert "PanicException" in str(exc.value)
    assert "toml" in str(exc.value)


def test_pattern_reports_its_metavariables(defs):
    assert defs.metavariables() == {"NAME", "ARGS", "BODY"}


def test_agreement_digest_is_carried(defs):
    assert defs.agreement.verified is True
    assert defs.agreement.digest.startswith("sha256:")


# -- search -----------------------------------------------------------------

def test_find_all_returns_resolved_pydantree_nodes(defs):
    matches = defs.find_all(SOURCE)
    assert [m.node.type for m in matches] == \
        ["function_definition", "function_definition"]
    assert [m.captures["NAME"].text for m in matches] == ["greet", "free"]


def test_find_returns_the_first_match_or_none(defs, lang):
    assert defs.find(SOURCE).captures["NAME"].text == "greet"
    assert defs.find("x = 1\n") is None


def test_multi_metavariable_captures_are_a_tuple(defs):
    match = defs.find(SOURCE)
    assert isinstance(match.captures["ARGS"], tuple)
    assert isinstance(match.captures["NAME"], Span)


def test_spans_are_byte_offsets_over_utf8(defs):
    """The source holds a non-ASCII character before the second match, so a
    character offset would land in the wrong place here (§4.1, Phase 0)."""
    match = defs.find_all(SOURCE)[1]
    data = SOURCE.encode("utf-8")
    assert data[match.span.start_byte:match.span.end_byte].decode("utf-8") \
        == match.text
    assert match.text.startswith("def free")


def test_a_rule_object_searches_like_a_pattern(lang):
    rule = Rule(pattern="$OBJ.$METHOD($$$ARGS)",
                inside=Rule(kind="class_definition"))
    pat = Pattern(rule, language=lang)
    src = "class A:\n    def m(self):\n        return self.x.y()\n"
    assert len(pat.find_all(src)) == 1


def test_relational_operands_default_to_stop_by_end(lang):
    """ast-grep's own `stopBy` default is "neighbor" — the immediate parent
    only — so `inside=Rule(kind="class_definition")` would match nothing at
    all and report it as "no such code". This module defaults to "end", and
    emits the choice explicitly rather than hiding it.
    """
    rule = Rule(pattern="$X", inside=Rule(kind="class_definition"))
    assert rule.to_astgrep()["inside"]["stopBy"] == "end"


def test_stop_by_neighbor_is_still_reachable(lang):
    rule = Rule(pattern="$X",
                inside=Rule(kind="class_definition", stop_by="neighbor"))
    assert rule.to_astgrep()["inside"]["stopBy"] == "neighbor"


def test_a_match_serializes(defs):
    record = defs.find(SOURCE).record
    assert record["kind"] == "function_definition"
    assert record["captures"]["NAME"]["text"] == "greet"
    assert record["agreement"].startswith("sha256:")


# -- the OutputModel bridge (§10) -------------------------------------------

class Server(OutputModel):
    """A record-mode model over the JSON pair shape.

    022 §10 illustrates the bridge with a Python `function_definition`. That
    example cannot work: pydantree's record mode is defined over key/value
    PAIR grammars, and a Python function is not a pair shape. The bridge
    itself is real — it just needs a grammar where record mode is defined.
    """

    __match__ = M("object", record=True)
    host: str
    port: int


@pytest.fixture
def json_lang():
    tree_sitter_json = pytest.importorskip("tree_sitter_json")
    # `tree_sitter.Language.name` is None for this wheel, so the ast-grep
    # identifier cannot be guessed and must be given (§7).
    return Language.from_module(tree_sitter_json, astgrep_name="json")


def test_extract_scopes_a_record_model_to_the_match(json_lang):
    """The payoff of putting this in pydantree: ast-grep locates by shape,
    pydantree types the result. Neither does the other's job."""
    with pytest.warns(UserWarning):        # json has no agreement record yet
        pat = Pattern(Rule(kind="object"), language=json_lang)
    src = '[{"host": "x", "port": 1}, {"host": "y", "port": 2}]'
    rows = [row for m in pat.find_all(src) for row in m.extract(Server)]
    assert [(r.host, r.port) for r in rows] == [("x", 1), ("y", 2)]


def test_extract_refuses_a_field_mode_model(defs):
    """A field-mode model carries an anchored path over the whole tree, which
    is the opposite of scoping to one match. Say so, do not silently do
    something else."""
    class Calls(OutputModel):
        __match__ = M("module", ..., "call")
        fn: str = capture("function")

    with pytest.raises(PatternError) as exc:
        defs.find(SOURCE).extract(Calls)
    assert "FIELD-mode" in str(exc.value)


def test_an_unrecorded_language_warns_but_still_works(json_lang):
    """Warnings are DATA on the object, surfaced once at bind (§4.2)."""
    with pytest.warns(UserWarning):
        pat = Pattern(Rule(kind="object"), language=json_lang)
    assert pat.agreement.verified is False
    assert any("no grammar-agreement record" in w for w in pat.warnings)


def test_one_parse_is_shared_by_every_match(defs):
    matches = defs.find_all(SOURCE)
    assert matches[0]._parse is matches[1]._parse


# -- resolution (§4.1) ------------------------------------------------------

def test_resolution_raises_rather_than_guessing(defs, lang):
    """Construct a divergence deliberately and assert the error, NOT a
    plausible neighbouring node.

    The two grammars agree today (Phase 0: 0 failures), so the divergence is
    injected: a byte range that no node spans exactly.
    """
    from pydantree_sitter.pattern import _Parse
    parse = _Parse(lang, SOURCE)
    with pytest.raises(PatternResolutionError) as exc:
        parse.resolve(3, 7, "identifier", pattern="$X", agreement="sha256:test")
    error = exc.value
    assert error.start_byte == 3 and error.end_byte == 7
    assert error.agreement == "sha256:test"
    assert error.nearest_kind is not None      # diagnostic only, never returned
    assert "disagree" in str(error)


def test_a_kind_disagreement_on_an_exact_range_still_raises(defs, lang):
    """Same range, wrong kind: several nodes can share one byte range, so
    picking by position alone would be a guess."""
    from pydantree_sitter.pattern import _Parse
    parse = _Parse(lang, SOURCE)
    node = parse.tree.root_node
    with pytest.raises(PatternResolutionError) as exc:
        parse.resolve(node.start_byte, node.end_byte, "not_a_real_kind",
                      pattern="$X", agreement="d")
    assert "pydantree's grammar has" in str(exc.value)


# -- rewrite (§8) -----------------------------------------------------------

def test_replace_all_returns_edits_as_data(defs):
    result = defs.replace_all(SOURCE, "def $NAME($$$ARGS) -> None: $$$BODY")
    assert result.count == 2
    assert len(result.edits) == 2
    assert "def greet(self, name) -> None:" in result.new_source
    assert "def free(x, y=2) -> None:" in result.new_source
    assert result.agreement.startswith("sha256:")


def test_count_is_the_true_match_count(defs):
    """`codeman`'s expected_matches contract depends on this number."""
    assert defs.replace_all(SOURCE, "def $NAME($$$ARGS): $$$BODY").count \
        == len(defs.find_all(SOURCE))


def test_edits_survive_non_ascii_source(lang):
    """Right-to-left byte splicing, over a buffer where character offsets and
    byte offsets differ."""
    pat = Pattern("$A + $B", language=lang)
    src = 'x = "h\u00e9llo " + name\ny = "\u00e9\u00e9" + z\n'
    result = pat.replace_all(src, "concat($A, $B)")
    assert result.count == 2
    assert 'concat("h\u00e9llo ", name)' in result.new_source
    assert 'concat("\u00e9\u00e9", z)' in result.new_source


def test_a_template_metavariable_the_pattern_does_not_bind_is_refused(defs):
    with pytest.raises(PatternRewriteError) as exc:
        defs.replace_all(SOURCE, "def $NAME($$$ARGS) -> $RETURN: $$$BODY")
    assert "$RETURN" in str(exc.value)
    assert "The pattern binds" in str(exc.value)


def test_overlapping_edits_are_refused_never_resolved(lang):
    """A chained call matches nested occurrences. Refusing is the specified
    behaviour — picking one would be a guess about intent (§17.8)."""
    pat = Pattern("$OBJ.$METHOD($$$ARGS)", language=lang)
    src = "a.b().c()\n"
    assert len(pat.find_all(src)) == 2          # nested, by construction
    with pytest.raises(PatternRewriteError) as exc:
        pat.replace_all(src, "$OBJ.$METHOD()")
    assert "overlapping edits" in str(exc.value)
    assert "Narrow the rule" in str(exc.value)


def test_a_rewrite_that_breaks_the_parse_raises(lang):
    """§8.1 — the single strongest safety property the module offers a
    consumer that cannot inspect its own edit."""
    pat = Pattern("$A = $B", language=lang)
    with pytest.raises(PatternRewriteError) as exc:
        pat.replace_all("x = 1\n", "$A = = $B")
    assert "does not parse" in str(exc.value)
    assert "NOT applied" in str(exc.value)


def test_source_that_was_already_broken_stays_rewritable(lang):
    """Only a NEW error is the module's fault."""
    pat = Pattern("$A = $B", language=lang)
    result = pat.replace_all("x = 1\ndef (:\n", "$A = 2")
    assert "x = 2" in result.new_source


def test_no_match_is_not_an_error(defs):
    result = defs.replace_all("x = 1\n", "def $NAME($$$ARGS): $$$BODY")
    assert result.count == 0
    assert result.new_source == "x = 1\n"


def test_single_line_matches_round_trip_exactly(lang):
    """§15's round-trip check, restricted to matches that do not span a
    newline.

    The general claim is FALSE, and not only here: a `$$$BODY` that covers an
    indented block loses its leading newline and indent, because the template
    puts a literal space where the source had a line break. The `ast-grep`
    CLI produces the identical collapse, so this is ast-grep's template
    semantics, not a defect in this module.

    `test_pattern_roundtrip.py` carries the invariant that DOES hold over the
    whole corpus: equality after a formatter pass.
    """
    src = "a = 1\nb = 2\nc = 3\n"
    pat = Pattern("$A = $B", language=lang)
    assert pat.replace_all(src, "$A = $B").new_source == src


def test_an_edit_that_leaks_into_its_surroundings_is_refused(lang):
    """The failure `has_error` cannot see.

    Collapsing a two-statement body onto the `def` line leaves the second
    statement stranded at the old indent. CPython calls that a SyntaxError.
    tree-sitter does NOT: it recovers by reparenting the stranded statement
    to MODULE level and reports a clean tree, so the code silently changes
    meaning. Measured over this package's source, the tree-sitter tier missed
    19 of 19 broken rewrites.
    """
    src = "def f(a):\n    x = 1\n    return x\n"
    broken = "def f(a): x = 1\n    return x\n"

    # the premise: tree-sitter really does accept it, and really does move
    # `return x` out of the function
    assert lang.parse(broken.encode()).root_node.has_error is False
    assert str(lang.parse(broken.encode()).root_node).count("return_statement") == 1
    import ast
    with pytest.raises(SyntaxError):
        ast.parse(broken)

    pat = Pattern("def $NAME($$$ARGS): $$$BODY", language=lang)
    with pytest.raises(PatternRewriteError) as exc:
        pat.replace_all(src, "def $NAME($$$ARGS): $$$BODY")
    assert "python parser rejects" in str(exc.value)
    assert "NOT applied" in str(exc.value)


def test_the_structural_proxy_catches_it_too_without_a_syntax_check(lang):
    """The fallback tier, for a language with no real parser to hand. It is
    weaker — it over-refuses — which is why it is not the default where a
    `syntax_check` exists."""
    no_check = Language.from_module(tree_sitter_python, syntax_check=False)
    assert no_check.syntax_check is None          # False disables the registry
    assert Language.from_module(tree_sitter_python).syntax_check is not None

    pat = Pattern("def $NAME($$$ARGS): $$$BODY", language=no_check)
    with pytest.raises(PatternRewriteError) as exc:
        pat.replace_all("def f(a):\n    x = 1\n    return x\n",
                        "def $NAME($$$ARGS): $$$BODY")
    # the proxy is the AUTO default here, because there is no parser to ask
    assert "not a single node" in str(exc.value)


def test_a_multi_statement_replacement_is_allowed(lang):
    """The restriction the structural proxy imposed, lifted.

    One statement becoming two is legitimate and common. It is structurally
    IDENTICAL to the broken collapse above — two top-level nodes where there
    was one — and only the language's own parser can tell them apart.
    """
    pat = Pattern("$A = $B", language=lang)
    result = pat.replace_all("x = 1\n", "$A = $B\nlog($A)")
    assert result.new_source == "x = 1\nlog(x)\n"
    assert result.diagnostics == ()


def test_forcing_the_structural_proxy_rejects_that_same_rewrite(lang):
    """...and the proxy proves it cannot: `single_node=True` refuses the
    valid rewrite above. This is why it is not the default."""
    pat = Pattern("$A = $B", language=lang)
    with pytest.raises(PatternRewriteError):
        pat.replace_all("x = 1\n", "$A = $B\nlog($A)", single_node=True)


def test_validate_false_returns_the_edits_with_the_diagnosis(lang):
    """A dry run: the caller gets the data AND the finding, and decides."""
    pat = Pattern("def $NAME($$$ARGS): $$$BODY", language=lang)
    result = pat.replace_all("def f(a):\n    x = 1\n    return x\n",
                             "def $NAME($$$ARGS): $$$BODY", validate=False)
    assert result.count == 1
    assert result.edits
    assert len(result.diagnostics) == 1
    assert "python parser rejects" in result.diagnostics[0]


def test_json_gets_a_syntax_check_too(json_lang):
    import json

    assert json_lang.syntax_check is not None
    json_lang.syntax_check('{"a": 1}')
    with pytest.raises(json.JSONDecodeError):
        json_lang.syntax_check("{not json}")


def test_an_explicit_syntax_check_wins(lang):
    calls = []

    def always_ok(source):
        calls.append(source)

    other = Language.from_module(tree_sitter_python, syntax_check=always_ok)
    assert other.syntax_check is always_ok
    pat = Pattern("def $NAME($$$ARGS): $$$BODY", language=other)
    # the broken collapse now passes, because the caller said it is valid
    result = pat.replace_all("def f(a):\n    x = 1\n    return x\n",
                             "def $NAME($$$ARGS): $$$BODY")
    assert result.count == 1 and calls


# -- on_overlap -------------------------------------------------------------

def test_on_overlap_outermost_keeps_the_widest_match(lang):
    pat = Pattern("$OBJ.$METHOD($$$ARGS)", language=lang)
    src = "a.b().c()\n"
    assert len(pat.find_all(src)) == 2
    result = pat.replace_all(src, "CALL", on_overlap="outermost")
    assert result.count == 2                # the true match count, unchanged
    assert result.dropped_for_overlap == 1
    assert result.new_source == "CALL\n"


def test_on_overlap_innermost_keeps_the_narrowest_match(lang):
    pat = Pattern("$OBJ.$METHOD($$$ARGS)", language=lang)
    result = pat.replace_all("a.b().c()\n", "CALL", on_overlap="innermost")
    assert result.dropped_for_overlap == 1
    assert result.new_source == "CALL.c()\n"


def test_on_overlap_refuse_is_still_the_default(lang):
    pat = Pattern("$OBJ.$METHOD($$$ARGS)", language=lang)
    with pytest.raises(PatternRewriteError):
        pat.replace_all("a.b().c()\n", "$OBJ.$METHOD()")


def test_an_unknown_overlap_policy_is_rejected_by_name(lang):
    pat = Pattern("$A = $B", language=lang)
    with pytest.raises(PatternRewriteError) as exc:
        pat.replace_all("x = 1\n", "$A = $B", on_overlap="whatever")
    assert "'outermost'" in str(exc.value)


# -- reindent ---------------------------------------------------------------

def test_reindent_fixes_a_multi_line_template(lang):
    """A multi-line template spliced at column 4 would otherwise put its
    second line at column 0."""
    src = "def f(c):\n    if c:\n        go()\n"
    pat = Pattern("if $C:\n    $$$B", language=lang)
    plain = pat.replace_all(src, "if not $C:\n    pass\nelse:\n    $$$B",
                            validate=False)       # it produces invalid Python
    assert "\nelse:" in plain.new_source          # at column 0 — wrong
    assert plain.diagnostics
    fixed = pat.replace_all(src, "if not $C:\n    pass\nelse:\n    $$$B",
                            reindent=True)
    assert "\n    else:" in fixed.new_source      # at the match's column
    import ast
    ast.parse(fixed.new_source)


def test_reindent_does_not_rescue_a_collapsed_body(lang):
    """Honest scope: a template writing `: $$$BODY` asks for the body on the
    header line, and the ast-grep CLI collapses it identically. reindent is
    for multi-line TEMPLATES, not for that."""
    pat = Pattern("def $NAME($$$ARGS): $$$BODY", language=lang)
    with pytest.raises(PatternRewriteError):
        pat.replace_all("def f(a):\n    x = 1\n    return x\n",
                        "def $NAME($$$ARGS): $$$BODY", reindent=True)


def test_a_single_statement_body_still_collapses_cleanly(lang):
    """The gate rejects a LEAK, not a collapse: one statement on the `def`
    line is valid Python and stays allowed."""
    pat = Pattern("def $NAME($$$ARGS): $$$BODY", language=lang)
    result = pat.replace_all("def f(a):\n    return a\n",
                             "def $NAME($$$ARGS): $$$BODY")
    assert result.new_source == "def f(a): return a\n"


# -- the edit arithmetic ----------------------------------------------------

def test_right_to_left_application_matches_a_naive_reference():
    """Right-to-left offset arithmetic is where this module would have its
    bug (§15), so it is checked against a left-to-right reference that
    tracks the drift explicitly."""
    source = "aaaa bbbb cccc dddd"
    edits = (
        Edit(start_byte=0, end_byte=4, new_text="W"),
        Edit(start_byte=5, end_byte=9, new_text="XXXXXXX"),
        Edit(start_byte=15, end_byte=19, new_text=""),
    )
    data = source.encode("utf-8")
    drift = 0
    for edit in sorted(edits, key=lambda e: e.start_byte):
        new = edit.new_text.encode("utf-8")
        data = data[:edit.start_byte + drift] + new + data[edit.end_byte + drift:]
        drift += len(new) - (edit.end_byte - edit.start_byte)
    assert _apply(source, edits) == data.decode("utf-8")


def test_adjacent_edits_do_not_count_as_overlapping():
    """`end` is exclusive: touching edits are legal."""
    _reject_overlap((Edit(start_byte=0, end_byte=4, new_text="x"),
                     Edit(start_byte=4, end_byte=8, new_text="y")))


def test_overlap_is_detected_regardless_of_input_order():
    with pytest.raises(PatternRewriteError):
        _reject_overlap((Edit(start_byte=4, end_byte=8, new_text="y"),
                         Edit(start_byte=0, end_byte=6, new_text="x")))
