"""`pydantree_sitter.rules` — the validated ast-grep rule model (022 §6).

Pure Pydantic: nothing here needs `ast_grep_py` or a parser. Every validator
has a rejecting case asserted on the MESSAGE, not only on the class (022
§15) — the message is the whole product for an untrusted caller that must
learn what it did wrong in one round trip.
"""

from __future__ import annotations

import pytest

from pydantree_sitter.errors import PatternBuildError
from pydantree_sitter.rules import (
    MAX_PATTERN_LENGTH,
    MAX_RULE_DEPTH,
    MAX_RULE_NODES,
    Rule,
    metavariables_of,
)

# -- emission ---------------------------------------------------------------

def test_keyword_fields_emit_by_alias():
    """`all`/`any`/`not` are Python keywords, so the fields carry a trailing
    underscore — the JSON must not."""
    rule = Rule(pattern="x", **{"not": Rule(kind="k")})
    assert rule.to_astgrep() == {"pattern": "x", "not": {"kind": "k"}}


def test_both_spellings_construct():
    assert Rule(not_=Rule(kind="k")).to_astgrep() == \
        Rule(**{"not": Rule(kind="k")}).to_astgrep()


def test_unset_keys_are_dropped():
    """The emitted dict is the rule the caller wrote and nothing else."""
    assert Rule(kind="call").to_astgrep() == {"kind": "call"}


def test_composite_lists_emit_as_lists():
    rule = Rule(any=[Rule(kind="a"), Rule(kind="b")])
    assert rule.to_astgrep() == {"any": [{"kind": "a"}, {"kind": "b"}]}


def test_extra_keys_are_forbidden():
    """`extra="forbid"`: a misspelled key is rejected, not silently ignored.
    pydantic raises its own ValidationError here — the typo never reaches a
    pydantree validator."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Rule(patern="typo")


# -- metavariables ----------------------------------------------------------

def test_metavariables_ignore_arity():
    """`$$$ARGS` and `$ARGS` both report the bare name: the caller is asking
    what the rule binds, not with what arity."""
    assert metavariables_of("$A.$B($$$C)") == {"A", "B", "C"}


def test_non_capturing_metavariable_is_excluded():
    """`$_X` binds nothing, so naming it in a template is an error."""
    assert metavariables_of("$A + $_IGNORED") == {"A"}


def test_lowercase_is_not_a_metavariable():
    assert metavariables_of("$a = $B") == {"B"}


def test_metavariables_walk_the_whole_tree():
    rule = Rule(pattern="$OUTER", inside=Rule(pattern="def $INNER(): pass"))
    assert rule.metavariables() == {"OUTER", "INNER"}


# -- validation -------------------------------------------------------------

def test_empty_rule_is_rejected():
    with pytest.raises(PatternBuildError) as exc:
        Rule()
    assert "empty rule" in str(exc.value)
    assert "pattern, kind, regex" in str(exc.value)


def test_relational_only_rule_is_rejected_with_the_reason():
    """A relational key constrains a match; it does not make one. The message
    must say that, because `inside=` alone looks plausible."""
    with pytest.raises(PatternBuildError) as exc:
        Rule(inside=Rule(kind="class_definition"))
    assert "only relational key(s) inside" in str(exc.value)
    assert "does not make one" in str(exc.value)


def test_uncompilable_regex_is_rejected_by_message():
    with pytest.raises(PatternBuildError) as exc:
        Rule(regex="((")
    assert "does not compile" in str(exc.value)


def test_depth_limit(  ):
    rule = Rule(kind="k")
    for _ in range(MAX_RULE_DEPTH - 1):
        rule = Rule(kind="k", inside=rule)          # at the limit, still fine
    with pytest.raises(PatternBuildError) as exc:
        Rule(kind="k", inside=rule)
    assert f"over the {MAX_RULE_DEPTH} limit" in str(exc.value)


def test_width_limit_is_a_separate_axis():
    """Depth is not the only bound an untrusted payload needs: a flat rule
    can be arbitrarily wide."""
    wide = [Rule(kind="k") for _ in range(MAX_RULE_NODES + 1)]
    with pytest.raises(PatternBuildError) as exc:
        Rule(any=wide)
    assert "sub-rules" in str(exc.value)


def test_pattern_length_limit():
    with pytest.raises(PatternBuildError) as exc:
        Rule(pattern="x" * (MAX_PATTERN_LENGTH + 1))
    assert f"over the {MAX_PATTERN_LENGTH} limit" in str(exc.value)


# -- the grammar check ------------------------------------------------------

class _Schema:
    """The two `NodeSchema` methods `check_kinds` uses."""
    name = "python"

    def kinds(self):
        return {"function_definition", "class_definition", "call"}


def test_unknown_kind_is_rejected_by_name():
    with pytest.raises(PatternBuildError) as exc:
        Rule(kind="function_defintion").check_kinds(_Schema())
    assert "'function_defintion'" in str(exc.value)


def test_unknown_kind_suggests_a_near_miss():
    """One round trip is the budget: the message must carry the fix."""
    with pytest.raises(PatternBuildError) as exc:
        Rule(kind="function_defintion").check_kinds(_Schema())
    assert "function_definition" in str(exc.value).split("Did you mean")[1]


def test_kind_check_reaches_nested_rules():
    rule = Rule(pattern="$X", inside=Rule(kind="nope"))
    with pytest.raises(PatternBuildError) as exc:
        rule.check_kinds(_Schema())
    assert "'nope'" in str(exc.value)


def test_known_kinds_pass():
    Rule(kind="call", inside=Rule(kind="class_definition")).check_kinds(_Schema())
