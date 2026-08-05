"""The rule-class surface (`tsgrammar.rules`) — tests.

The load-bearing test is THE GATE: the class-authored devenv grammar
(`tests/fixtures/devenv_classes_grammar.py`) must emit grammar.json
DEEP-EQUAL to the builder-DSL spelling (`examples/devenv-subset/grammar.py`).
The surface is faithful sugar over the existing builder — any mapping row
(field placement, token wrapping, flag reading, helper output) that drifts
from the DSL's IR fails here first.

The full mapping matrix + surface rules land here too (REFACTOR step 6).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

import tsgrammar as tg

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent
FIXTURES = TESTS / "fixtures"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# the gate: class-authored == builder-DSL grammar.json
# ---------------------------------------------------------------------------

def _ir_dict(build):
    """Grammar.build() -> the IR as a plain dict (the probe convention:
    model_dump_json(exclude_none=True), parsed — formatting-free deep equal)."""
    return json.loads(build().build().model_dump_json(exclude_none=True))


def test_gate_devenv_class_grammar_identical_to_builder_dsl():
    """THE GATE — byte-identity. The same grammar authored two ways must emit
    the same grammar.json: rule order, externals, extras, flags, and every
    regex string in the IR."""
    classes = _load_module(
        "devenv_classes_grammar", FIXTURES / "devenv_classes_grammar.py")
    example = _load_module(
        "devenv_example_grammar", REPO / "examples" / "devenv-subset" /
        "grammar.py")

    new = _ir_dict(classes.build)
    old = _ir_dict(example.build)
    assert new == old
    assert list(new["rules"]) == list(old["rules"])
    assert len(new["rules"]) == 17

    # the assembled grammar passes the checks the DSL version passes
    assert not tg.errors(classes.build())
    assert not tg.errors(example.build())


def test_gate_rule_order_matches_example():
    """Rule registration order (definition order) + start-first reordering
    matches the builder-DSL file exactly (the CLI's root + pruning contract)."""
    classes = _load_module(
        "devenv_classes_grammar2", FIXTURES / "devenv_classes_grammar.py")
    g = classes.build()
    m = g.build()
    assert list(m.rules)[0] == "source_file"
    assert list(m.rules)[1:] == [
        "comment", "name_path", "number", "path_literal", "string_fragment",
        "indented_string_fragment", "interpolation", "string",
        "indented_string", "pair", "attrset", "list", "with_expr", "value",
        "formal", "formals",
    ]


def test_gate_external_and_extra_placement():
    """Externals (definition order, SCREAMING_SNAKE default) and the comment
    extra land exactly where the DSL file puts them."""
    classes = _load_module(
        "devenv_classes_grammar3", FIXTURES / "devenv_classes_grammar.py")
    m = classes.build().build()
    assert [e.type for e in m.externals] == ["TOKEN", "TOKEN"]
    assert [e.content.value for e in m.externals] == [
        "STRING_FRAGMENT", "INDENTED_STRING_FRAGMENT"]
    # extras: the builder prepends the whitespace default; then the comment
    assert len(m.extras) == 2
    assert m.extras[0].value == r"\s"
    assert m.extras[1].type == "SYMBOL" and m.extras[1].name == "comment"
    assert m.supertypes == ["value"]
    assert m.word is None
    assert m.inline == []
