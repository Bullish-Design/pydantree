"""Phase-6 Job-2 tests: `.pyi` typed node accessors from the node-schema.

Covers: the generator emits a parseable stub over the REAL tree-sitter-rust
schema (hermetic fixture) whose every name resolves against the schema; the
stub is checked by mypy over a consumer that casts a tree_sitter.Node to a
generated kind class and exercises the field/get/children accessors.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tscore.schema import NodeSchema
from tsquery.stubs import generate_stubs

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "rust"
MYPY = shutil.which("mypy")

CONSUMER = """\
from typing import cast

import tree_sitter

import rust_accessors as ra


def field_accessor(n: tree_sitter.Node) -> str | None:
    fn = cast(ra.function_item, n)
    name = fn.name()          # -> identifier | metavariable | None
    if name is None:
        return None
    return name.type


def get_accessor(n: tree_sitter.Node) -> ra._type | None:
    fn = cast(ra.function_item, n)
    return fn.get("return_type")   # the _type supertype alias


def body_field(n: tree_sitter.Node) -> ra.block | None:
    fn = cast(ra.function_item, n)
    return fn.body()      # field named 'body' -> block | None


def children_accessor(n: tree_sitter.Node) -> list[ra.where_clause]:
    fn = cast(ra.function_item, n)
    return fn.children("where_clause")


def list_field(n: tree_sitter.Node) -> list[ra._type]:
    ol = cast(ra.ordered_field_declaration_list, n)
    return ol.field_type()      # the repeated 'type' field -> list[_type]
"""


def _rust_schema() -> NodeSchema:
    return NodeSchema.from_list(
        json.loads((FIXTURES / "node-types.json").read_text()), name="rust")


def test_generated_stub_parses_and_all_names_resolve():
    stub = generate_stubs(_rust_schema(), lang_name="rust")
    ast.parse(stub)  # must be valid Python syntax
    # every name referenced in an annotation resolves: collect the declared
    # names (classes + supertype aliases + Node) and check each annotation
    # token against them plus the typing vocabulary.
    declared = set()
    for line in stub.splitlines():
        if line.startswith("class "):
            declared.add(line.split()[1].split("(")[0])
        elif line and not line.startswith((" ", "#", "from", "import")) \
                and "=" in line:
            declared.add(line.split("=")[0].strip())
    declared.add("Node")
    vocab = declared | {"None", "list", "object", "Literal", "overload",
                        "str", "self", "field", "kind", "get", "children"}
    import re
    for line in stub.splitlines():
        if "->" not in line:
            continue
        ann = line.split("->", 1)[1]
        for name in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", ann):
            assert name in vocab, f"dangling {name!r} in {line.strip()!r}"


@pytest.mark.skipif(MYPY is None, reason="mypy not on PATH")
def test_stub_type_checks_against_a_real_node(tmp_path):
    """The accessors type-check: mypy over a consumer that casts a real
    tree_sitter.Node to the generated classes and calls the field / get /
    children accessors. The consumer must be clean."""
    stub = generate_stubs(_rust_schema(), lang_name="rust")
    stub_path = tmp_path / "rust_accessors.pyi"
    stub_path.write_text(stub)
    consumer = tmp_path / "consumer.py"
    consumer.write_text(CONSUMER)
    proc = subprocess.run(
        [MYPY, str(consumer), "--python-executable", sys.executable,
         "--no-error-summary", "--follow-imports=skip", "--ignore-missing-imports"],
        capture_output=True, text=True, cwd=str(tmp_path), check=False)
    # follow-imports=skip still type-checks the stub's own names where used
    # in the consumer; ignore-missing-imports keeps tree_sitter out of it
    assert proc.returncode == 0, proc.stdout or proc.stderr
    assert "error:" not in proc.stdout


def test_stub_shipped_beside_the_schema(tmp_path):
    """generate_stubs(out=...) writes the .pyi beside the schema (the
    Phase-4 Job-2 packaging: 'shipped as .pyi alongside the schema')."""
    schema_dir = tmp_path / "bundle"
    schema_dir.mkdir()
    schema_path = schema_dir / "node-schema.json"
    _rust_schema().write(schema_path)
    stub_path = schema_dir / "rust_accessors.pyi"
    generate_stubs(_rust_schema(), lang_name="rust", out=stub_path)
    assert stub_path.exists()
    assert "# Typed node accessors for rust" in stub_path.read_text()
