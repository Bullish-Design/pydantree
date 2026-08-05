"""codegen tests: REAL typed CST accessors from the node-schema (014 §5, D7).

The old stubs.py was typing fiction (F-A4): the accessors type-checked but
didn't exist at runtime. The generated module now RUNS: module execs over
the real rust schema, `wrap()` round-trips against raw
`child_by_field_name`, and a mypy run over a consumer sees real runtime
code.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

from pydantree_sitter.codegen import generate_typed_api
from pydantree_sitter.schema import NodeSchema

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "rust"
MYPY = shutil.which("mypy")

requires_toolchain = pytest.mark.toolchain


def _rust_schema() -> NodeSchema:
    return NodeSchema.from_list(
        json.loads((FIXTURES / "node-types.json").read_text()), name="rust")


def _exec_module(src: str, name: str):
    mod = types.ModuleType(name)
    exec(compile(src, f"{name}.py", "exec"), mod.__dict__)
    return mod


def test_generated_module_execs_over_real_rust():
    mod = _exec_module(generate_typed_api(_rust_schema(), "rust_api"),
                       "rust_api")
    # every named kind is in KIND_MAP; wrap() dispatches on node.type
    assert "function_item" in mod.KIND_MAP
    assert mod.KIND_MAP["function_item"].KIND == "function_item"
    assert mod.wrap(None) is None


@requires_toolchain
def test_runtime_round_trip_matches_raw_child_by_field_name(tmp_path):
    """parse real rust source, wrap() the tree, walk fields — the typed
    accessor values equal the raw child_by_field_name lookups."""
    import tree_sitter
    from pydantree_sitter.loader import load_grammar_so
    from pydantree_sitter_grammar.schema_tool import build_community_bundle

    bundle = build_community_bundle(FIXTURES, tmp_path / "bundle",
                                    name="rust", keep=True)
    lang, _lib = load_grammar_so(bundle / "grammar.so", "rust")
    parser = tree_sitter.Parser(lang)
    src = b"fn add(a: i32, b: i32) -> i32 {\n    a + b\n}\nstruct Point(f64, f64);\n"
    tree = parser.parse(src)
    mod = _exec_module(generate_typed_api(_rust_schema(), "rust_api"),
                       "rust_api")

    fn = None
    raw_fn = None
    for n in tree.root_node.children:
        if n.type == "function_item":
            fn = mod.wrap(n)
            raw_fn = n
    assert fn is not None and raw_fn is not None
    assert fn.kind == "function_item"

    # field accessors == raw child_by_field_name
    raw_name = raw_fn.child_by_field_name("name")
    assert fn.name is not None and fn.name.node == raw_name
    assert fn.name.text == "add"
    raw_params = raw_fn.child_by_field_name("parameters")
    assert fn.parameters.node == raw_params

    # the children(kind) accessor over the positional children summary
    raw_param_count = sum(
        1 for c in raw_params.children if c.type == "parameter")
    assert len(fn.parameters.children("parameter")) == raw_param_count

    # a repeated FIELD accessor (rust's ordered_field_declaration_list has
    # a repeated `type` field): the tuple struct's fields
    ofdl = None
    for n2 in tree.root_node.children:
        if n2.type == "ordered_field_declaration_list":
            ofdl = mod.wrap(n2)
            break
        for c in n2.children:
            if c.type == "ordered_field_declaration_list":
                ofdl = mod.wrap(c)
                break
    assert ofdl is not None
    raw_type_count = sum(
        1 for i in range(ofdl.node.child_count)
        if ofdl.node.field_name_for_child(i) == "type")
    assert len(ofdl.field_type) == raw_type_count == 2

    # line/kind/text properties work
    assert fn.line == 1
    assert "fn add" in fn.text


@pytest.mark.skipif(MYPY is None, reason="mypy not on PATH")
def test_typed_accessors_type_check_and_are_real(tmp_path):
    """mypy over a consumer that imports the GENERATED RUNTIME module (not a
    .pyi): the accessors type-check AND exist (the F-A4 fix — the old stubs
    type-checked code that would crash)."""
    mod_src = generate_typed_api(_rust_schema(), "rust_accessors")
    mod_path = tmp_path / "rust_accessors.py"
    mod_path.write_text(mod_src)
    consumer = tmp_path / "consumer.py"
    consumer.write_text('''\
from typing import cast

import tree_sitter

import rust_accessors as ra


def field_accessor(n: tree_sitter.Node) -> str | None:
    fn = cast(ra.FunctionItem, n)
    name = fn.name          # -> Identifier | None
    if name is None:
        return None
    return name.text


def repeated_field(n: tree_sitter.Node) -> list[ra.Type]:
    ol = cast(ra.OrderedFieldDeclarationList, n)
    return ol.field_type   # the repeated 'type' field -> list[Type]


def wrap_roundtrip(n: tree_sitter.Node) -> ra.TypedNode | None:
    return ra.wrap(n)
''')
    proc = subprocess.run(
        [MYPY, str(consumer), "--python-executable", sys.executable,
         "--no-error-summary", "--follow-imports=skip",
         "--ignore-missing-imports"],
        capture_output=True, text=True, cwd=str(tmp_path), check=False)
    assert proc.returncode == 0, proc.stdout or proc.stderr
    assert "error:" not in proc.stdout
    # the module imports cleanly (it is real code, not a stub)
    _exec_module(mod_src, "rust_accessors")


def test_acronym_aware_class_names():
    """F-B4-style naming: kinds -> camel class names (shared helper)."""
    from pydantree_sitter.codegen import class_name
    assert class_name("function_item") == "FunctionItem"
    assert class_name("_type") == "Type"
    assert class_name("http_server") == "HttpServer"


@requires_toolchain
def test_package_writes_typed_api_beside_the_schema(tmp_path):
    """write_bundle's Phase-3 hook: `package(..., typed_api=True)` drops a
    REAL typed_api.py beside the schema (the shipped typed-CST surface)."""
    import pydantree_sitter_grammar as tg
    g = tg.Grammar("codegen_t")
    g.rule("identifier", tg.pattern(r"[a-z]+"), word=True)
    g.rule("pair", tg.seq(tg.field("key", tg.ref("identifier")), ":",
                          tg.field("value", tg.ref("identifier"))))
    g.rule("source_file", tg.repeat(tg.ref("pair")))
    g.start("source_file")
    result = tg.build_builder(g)
    bundle = result.package(tmp_path / "bundle", typed_api=True)
    api = bundle / "typed_api.py"
    assert api.exists()
    mod = _exec_module(api.read_text(), "typed_api_test")
    assert "pair" in mod.KIND_MAP
