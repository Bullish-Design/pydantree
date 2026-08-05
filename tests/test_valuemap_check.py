"""A1 (REVIEW 018): the bind-time checker must consume the same
(schema, ValueMap) the emitter does — a committed ValueMap is declared data
(D6), never overruled by the name-regex heuristic."""

from pydantree_sitter.compiler import _kind_coerces, _scalar_of
from pydantree_sitter.schema import NodeSchema
from pydantree_sitter.valuemap import ValueMap


def _json_like_schema_with_named_int():
    """A JSON-ish grammar whose integer leaf is named `qty` — a name the
    `propose_value_map` heuristic does NOT recognize as numeric."""
    return NodeSchema.from_list([
        {"type": "document", "named": True, "fields": {}, "children":
         {"multiple": False, "required": True, "types": [{"type": "object", "named": True}]}},
        {"type": "object", "named": True, "fields": {}, "children":
         {"multiple": True, "required": False, "types": [{"type": "pair", "named": True}]}},
        {"type": "pair", "named": True, "fields": {"key": {"multiple": False, "required": True, "types": [{"type": "ident", "named": True}]},
                                                  "value": {"multiple": False, "required": True, "types": [{"type": "qty", "named": True}]}}},
        {"type": "ident", "named": True},
        {"type": "qty", "named": True},
    ])


def test_committed_valuemap_is_authoritative_in_the_check():
    schema = _json_like_schema_with_named_int()
    vm = ValueMap(scalars={"qty": "int"})
    # the checker must agree with the emitter: qty -> int (declared data wins)
    assert _scalar_of(schema, vm, "qty") == "int"
    # ...even though the draft heuristic alone would say "str" (regex misses
    # `qty`), which is exactly the false SchemaCheckError the review found
    assert _scalar_of(schema, None, "qty") == "str"
    assert _kind_coerces(schema, vm, int, "qty") is True
    assert _kind_coerces(schema, None, int, "qty") is False


def test_checker_matches_emitter_for_wrapper_kinds():
    """Record-mode emission for a str target accepts ValueMap wrapper kinds
    (wrapper -> text leaf); the checker's str branch must agree."""
    schema = _json_like_schema_with_named_int()
    vm = ValueMap(scalars={"qty": "int"}, wrappers={"ident": "text"})
    # `ident` is declared a string wrapper in the ValueMap (its schema entry
    # is a bare leaf, so the structural _text_shape also passes — this pins
    # that the wrapper declaration alone is enough, matching emission).
    assert _kind_coerces(schema, vm, str, "ident") is True
