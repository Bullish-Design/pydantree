"""Live checks for the older-review audit.

This probe intentionally records both successful output and the public
exception surface. It is run inside ``devenv shell`` because the schema-tool
check exercises the pinned tree-sitter CLI.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import tree_sitter_json
import tree_sitter_python

from pydantree_sitter import (
    ExtractionError,
    Language,
    M,
    OutputModel,
    TreeLanguageError,
    capture,
)
from pydantree_sitter.codegen import generate_typed_api
from pydantree_sitter.schema import NodeSchema
from pydantree_sitter_grammar.schema_tool import derive_schema_for_dir


def main() -> None:
    report: dict[str, object] = {}

    class Assignment(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        value: str = capture("right")

    py = Language.from_module(tree_sitter_python)
    report["same_language"] = [
        row.model_dump() for row in py.extractor(Assignment).extract("x = 1\n")
    ]
    foreign = Language.from_module(tree_sitter_json)
    try:
        py.extractor(Assignment).extract_tree(foreign.parse("{}"))
    except TreeLanguageError as exc:
        report["cross_language"] = {
            "exception": type(exc).__name__,
            "message": str(exc),
        }

    class Function(OutputModel):
        __match__ = M("module", "function_definition")
        name: str = capture("name")

    malformed: dict[str, object] = {}
    for label, source in (("error", "def f(1):\n"),
                          ("missing", "def f(:\n")):
        try:
            py.extractor(Function).extract(source)
        except ExtractionError as exc:
            failure = exc.failures[0]
            malformed[label] = {
                "exception": type(exc).__name__,
                "message": str(exc),
                "span": failure.span.text if failure.span else None,
                "detail": failure.detail,
                "lenient_rows": [
                    row.model_dump() for row in
                    py.extractor(Function, strict=False).extract(source)
                ],
            }
    report["malformed_cst"] = malformed

    cycle = NodeSchema.from_list([
        {"type": "a", "named": True,
         "subtypes": [{"type": "b", "named": True}]},
        {"type": "b", "named": True,
         "subtypes": [{"type": "a", "named": True}]},
    ])
    try:
        generate_typed_api(cycle, "cycle_api")
    except ValueError as exc:
        report["typed_api_cycle"] = {
            "exception": type(exc).__name__,
            "message": str(exc),
        }

    with tempfile.TemporaryDirectory(prefix="pydantree-audit-") as td:
        root = Path(td)
        workdir = root / "caller-work"
        workdir.mkdir()
        sentinel = workdir / "sentinel.txt"
        sentinel.write_text("keep me")
        schema = derive_schema_for_dir(
            Path("tests/fixtures/rust"),
            workdir=workdir,
            out=root / "node-schema.json",
        )
        report["caller_workdir"] = {
            "schema_kinds": len(schema.node_types),
            "workdir_exists": workdir.is_dir(),
            "sentinel_exists": sentinel.exists(),
            "sentinel_text": sentinel.read_text(),
        }

    import pydantree_sitter_grammar as tg

    namespace: dict[str, object] = {}
    exec("from pydantree_sitter_grammar import *", namespace)  # noqa: S102
    documented = {
        "write_bundle", "build_from_source_dir", "Toolchain",
        "derive_schema_for_dir", "build_community_bundle",
    }
    report["product_b_surface"] = {
        "star_import_ok": all(name in namespace for name in documented),
        "missing_documented": sorted(name for name in documented
                                      if name not in namespace),
        "phantom_rule": "rule" in namespace,
        "all_count": len(tg.__all__),
    }

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
