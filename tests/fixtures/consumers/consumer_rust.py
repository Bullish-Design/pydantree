"""Run 2 — the community seam over a REAL grammar, B-free.

Consumes the tree-sitter-rust community bundle (built from the real grammar
SOURCE via pydantree_sitter_grammar.schema_tool.build_community_bundle) in a SEPARATE process
where pydantree_sitter_grammar is NOT importable. The schema was derived by the community
tool (byte-for-byte with the CLI's node-types.json); the checks are active;
the extraction rows must match the HAND-AUTHORED ground truth (written on
paper before the model, from the grammar's semantics).

Tasks:
  RustFn        — function definitions: name, return_type (optional), line.
  TupleStruct   — tuple struct field types: the repeated `type` field of
                  ordered_field_declaration_list as a field-mode list.

Usage: python consumer_rust.py <bundle-dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import pydantree_sitter_grammar  # noqa: F401
    print(json.dumps({"ok": False,
                      "error": "pydantree_sitter_grammar IS importable — B leaked"}))
    sys.exit(1)
except ModuleNotFoundError:
    pass

from pydantree_sitter import Language, M, OutputModel, capture, source_meta  # noqa: E402

RUST_SAMPLE = """\
// module doc
use std::collections::HashMap;

fn add(a: u32, b: u32) -> u32 {
    a + b
}

pub fn main() {
    let mut map = HashMap::new();
    map.insert("k", 1);
    println!("{}", map["k"]);
}

fn greet(name: &str) -> String {
    format!("Hello, {name}!")
}

struct Point(f64, f64);

struct Named {
    x: u32,
}

pub struct Tuple(i32, String, bool);

fn no_return() {}
"""

# hand-authored BEFORE the models (from the grammar's semantics, counted by
# hand over the sample): line = the node's start line (1-based)
FN_GROUND_TRUTH = [
    {"name": "add", "line": 4},
    {"name": "main", "line": 8},
    {"name": "greet", "line": 14},
    {"name": "no_return", "line": 26},
]
# functions WITH their return type — an Optional field-mode capture is now
# query-optional (Phase 6.5): `return_type: str | None = capture(...)` emits
# `return_type:(_)?`, so functions WITHOUT the field also match (None) — the
# Phase-6 finding (the field was silently required) is fixed
FN_RETURN_GROUND_TRUTH = [
    {"name": "add", "return_type": "u32", "line": 4},
    {"name": "main", "return_type": None, "line": 8},
    {"name": "greet", "return_type": "String", "line": 14},
    {"name": "no_return", "return_type": None, "line": 26},
]
TUPLE_GROUND_TRUTH = [
    {"name": "Point", "types": ["f64", "f64"], "line": 18},
    {"name": "Tuple", "types": ["i32", "String", "bool"], "line": 24},
]


class RustFn(OutputModel):
    """Function definitions: field-mode scalar captures."""

    __match__ = M("source_file", "function_item")
    name: str = capture("name")
    line: int = source_meta()


class RustFnReturn(OutputModel):
    """Functions with their return type: an Optional field-mode capture — the
    query emits `return_type:(_)?`, so functions WITHOUT one match with None
    (the Phase-6.5 fix; previously the field was silently required)."""

    __match__ = M("source_file", "function_item")
    name: str = capture("name")
    return_type: str | None = capture("return_type")
    line: int = source_meta()


class TupleStructTypes(OutputModel):
    """Tuple struct field types: the repeated `type` field of the
    ordered_field_declaration_list, merged as a field-mode list."""

    __match__ = M("source_file", "struct_item", "ordered_field_declaration_list")
    types: list[str] = capture("type")
    line: int = source_meta()


class StructName(OutputModel):
    """Struct names (to pair with the tuple types by line)."""

    __match__ = M("source_file", "struct_item")
    name: str = capture("name")
    line: int = source_meta()


def main() -> int:
    lang = Language.load_bundle(sys.argv[1])
    # the checks run BEFORE any text is parsed (the schema entry is cited on
    # a mismatch — e.g. `return_type` must exist on function_item)
    RustFn.validate_with(lang)
    RustFnReturn.validate_with(lang)
    TupleStructTypes.validate_with(lang)
    StructName.validate_with(lang)

    fns = [r.model_dump() for r in RustFn.extract(RUST_SAMPLE, language=lang)]
    with_ret = [r.model_dump() for r in
                RustFnReturn.extract(RUST_SAMPLE, language=lang)]
    tuples = [r.model_dump() for r in
              TupleStructTypes.extract(RUST_SAMPLE, language=lang)]
    names = {r.line: r.name for r in
             StructName.extract(RUST_SAMPLE, language=lang)}
    paired = [{"name": names.get(t["line"], "?"), "types": t["types"],
               "line": t["line"]} for t in tuples]

    ok = (fns == FN_GROUND_TRUTH) and (with_ret == FN_RETURN_GROUND_TRUTH) \
        and (paired == TUPLE_GROUND_TRUTH)
    print(json.dumps({
        "ok": ok,
        "fns": fns,
        "fns_with_return": with_ret,
        "tuple_structs": paired,
        "schema_bound": lang.schema is not None,
        "schema_kinds": len(lang.schema.kinds()) if lang.schema else None,
    }, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
