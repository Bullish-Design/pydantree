"""Behaviour oracle and query-vs-walk benchmark for Phase 024 item 6.

The direct implementation is deliberately local to this evidence probe. It
walks named children, applies the same anchor and resolver, and does not call
the query emitter or ``QueryCursor``.
"""

import importlib.metadata
import json
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Annotated

import tree_sitter_json
import tree_sitter_python

from pydantree_sitter import Grammar, Node
from pydantree_sitter.errors import QueryBuildError, SchemaCheckError
from pydantree_sitter.match import match_ancestor_path
from pydantree_sitter.nodes import Matches, normalize_under
from pydantree_sitter.raw import Query, RawQuery
from pydantree_sitter.schema import NodeSchema

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "evidence" / "2026-09-09"


def direct_find(raw, cls):
    """The smallest credible direct-tree-walk replacement prototype."""
    path = normalize_under((*tuple(getattr(cls, "__under__", ()) or ()), cls))
    rows = []

    def visit(candidate):
        if candidate.type == cls.__kind__ and match_ancestor_path(candidate, path):
            try:
                rows.append(cls.from_node(candidate))
            except Exception:  # noqa: BLE001 - match rejection in prototype
                rows.extend(())
        for child in candidate.named_children:
            visit(child)

    visit(raw)
    return rows


def dumps(rows):
    return [row.model_dump() for row in rows]


def grammar_for(name: str):
    if name == "python":
        schema = NodeSchema.from_node_types_json(
            ROOT / "examples/wheel-extract/vendor/python-node-types.json")
        return Grammar.load(tree_sitter_python.language(), schema)
    schema = NodeSchema.from_node_types_json(
        ROOT / "tests/fixtures/jsonlike/node-types.json")
    return Grammar.load(tree_sitter_json.language(), schema)


def oracle():
    py = grammar_for("python")

    class Assignment(py.nodes.Assignment):
        left: str
        right: str | None

    class Function(py.nodes.FunctionDefinition):
        name: str
        return_type: str | None

    class FunctionName(py.nodes.Identifier):
        __under__ = (py.nodes.Module, ..., py.nodes.FunctionDefinition)

    class RawAssignment(Node):
        __kind__ = "assignment"
        __raw_query__ = RawQuery(
            "(module (expression_statement (assignment "
            "left: (identifier) @name right: (_) @value)))")
        name: str
        value: str

    source = (ROOT / "examples/wheel-extract/corpus.py").read_text()
    tree = py.parse(source)
    cases = {
        "root_and_nested": py.nodes.Module,
        "repeated_field_capture": Assignment,
        "optional_missing_node": Function,
        "ancestor_context": FunctionName,
        "broad_match": py.nodes.Identifier,
        "raw_query": RawAssignment,
    }
    result = {}
    for name, cls in cases.items():
        query_rows = tree.find(cls)
        if getattr(cls, "__raw_query__", None) is not None:
            result[name] = {
                "rows": dumps(query_rows),
                "query_source": py.query_source(cls),
                "coverage": "current raw-query escape hatch",
            }
            continue
        walk_rows = direct_find(tree.raw.root_node, cls)
        result[name] = {
            "equal": dumps(query_rows) == dumps(walk_rows),
            "rows": dumps(query_rows),
            "walk_rows": dumps(walk_rows),
            "query_source": py.query_source(cls),
        }
        assert result[name]["equal"], name

    json_grammar = grammar_for("json")

    class Pair(json_grammar.nodes.Pair):
        key: Annotated[str, Matches(r'"alice"')]
        value: str

    rows = json_grammar.parse('{"alice": 1, "bob": 2}').find(Pair)
    assert [row.key for row in rows] == ['"alice"']
    result["named_and_predicate_constraint"] = dumps(rows)

    failures = {}
    try:
        Query.raw("(no_such_kind)").compile(py.language)
    except QueryBuildError as error:
        failures["malformed_query"] = type(error).__name__
    try:
        class Bad(RawAssignment):
            __raw_query__ = RawQuery("(assignment) @unknown")

        tree.find(Bad)
    except (SchemaCheckError, QueryBuildError) as error:
        failures["incompatible_query"] = type(error).__name__
    assert set(failures) == {"malformed_query", "incompatible_query"}
    result["query_failures"] = failures
    return py, cases, result


def source_cases():
    cases = {
        "python_small": (
            tree_sitter_python.language(),
            NodeSchema.from_node_types_json(
                ROOT / "examples/wheel-extract/vendor/python-node-types.json"),
            "x = 1\n",
            "Assignment",
        ),
        "python_large": (
            tree_sitter_python.language(),
            NodeSchema.from_node_types_json(
                ROOT / "examples/wheel-extract/vendor/python-node-types.json"),
            (ROOT / "examples/wheel-extract/corpus.py").read_text() * 20,
            "Identifier",
        ),
        "json_medium": (
            tree_sitter_json.language(),
            NodeSchema.from_node_types_json(
                ROOT / "tests/fixtures/jsonlike/node-types.json"),
            "{" + ",".join(f'\"k{i}\": {i}' for i in range(100)) + "}",
            "Pair",
        ),
    }
    from pydantree_sitter_grammar.pipeline import build_from_source_dir, write_bundle

    for name, filename, kind in (
        ("bash_fixture", "sample.sh", "VariableAssignment"),
        ("nix_fixture", "mypi-agent.nix", "Binding"),
        ("rust_fixture", "functions.rs", "FunctionItem"),
        ("markdown_fixture", "headings.md", "AtxHeading"),
    ):
        fixture = ROOT / "tests/fixtures" / {
            "bash_fixture": "bash",
            "nix_fixture": "nix",
            "rust_fixture": "rust",
            "markdown_fixture": "markdown",
        }[name]
        bundle = write_bundle(
            build_from_source_dir(fixture), OUT / "bundles" / name)
        source_path = {
            "bash_fixture": ROOT / "examples/bash-extract" / filename,
            "nix_fixture": ROOT / "examples/devenv-extract/fleet" / filename,
            "rust_fixture": OUT / filename,
            "markdown_fixture": OUT / filename,
        }[name]
        if name == "rust_fixture":
            source_path.write_text(
                "fn add(a: u32, b: u32) -> u32 { a + b }\n" * 40)
        elif name == "markdown_fixture":
            source_path.write_text("# Title\n\n## Section\n" * 40)
        cases[name] = (bundle, None, source_path.read_text(), kind)
    return cases


def benchmark():
    records = []
    for case, values in source_cases().items():
        language, schema, source, kind = values
        if isinstance(language, Path):
            grammar = Grammar.load_bundle(language)
        else:
            grammar = Grammar.load(language, schema)
        cls = getattr(grammar.nodes, kind)
        encoded = source.encode()
        # Warm-up compiles the emitted query and exercises the same path used
        # by the measured repeated-query runs.
        parsed = grammar.parse(encoded)
        parsed.find(cls)
        for run in range(20):
            t0 = time.perf_counter_ns()
            tree = grammar.parse(encoded)
            query_rows = tree.find(cls)
            t1 = time.perf_counter_ns()
            query_only = tree.find(cls)
            t2 = time.perf_counter_ns()
            walk_rows = direct_find(tree.raw.root_node, cls)
            t3 = time.perf_counter_ns()
            assert dumps(query_rows) == dumps(walk_rows)
            records.extend([
                {"case": case, "run": run, "mode": "parse_plus_query",
                 "ns": t1 - t0, "rows": len(query_rows), "bytes": len(encoded)},
                {"case": case, "run": run, "mode": "warm_query_only",
                 "ns": t2 - t1, "rows": len(query_only), "bytes": len(encoded)},
                {"case": case, "run": run, "mode": "direct_walk_only",
                 "ns": t3 - t2, "rows": len(walk_rows), "bytes": len(encoded)},
            ])
            t4 = time.perf_counter_ns()
            for _ in range(10):
                tree.find(cls)
            t5 = time.perf_counter_ns()
            records.append({"case": case, "run": run,
                            "mode": "ten_warm_queries_one_tree",
                            "ns": t5 - t4, "rows": len(query_rows),
                            "bytes": len(encoded)})
    return records


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    py, _, behavior = oracle()
    records = benchmark()
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "tree_sitter": importlib.metadata.version("tree-sitter"),
        "python_language": py.language.name,
        "cwd": str(ROOT),
    }
    (OUT / "behavior-oracle.json").write_text(json.dumps(behavior, indent=2) + "\n")
    (OUT / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    with (OUT / "timings.jsonl").open("w") as stream:
        for record in records:
            stream.write(json.dumps(record) + "\n")
    summary = {}
    for case in sorted({record["case"] for record in records}):
        summary[case] = {}
        for mode in ("parse_plus_query", "warm_query_only", "direct_walk_only",
                     "ten_warm_queries_one_tree"):
            values = [record["ns"] / 1e6 for record in records
                      if record["case"] == case and record["mode"] == mode]
            summary[case][mode] = {
                "median_ms": statistics.median(values),
                "min_ms": min(values),
                "max_ms": max(values),
                "stdev_ms": statistics.stdev(values),
            }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"behavior": behavior, "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
