"""Public-API oracle: find_in(query) vs find_in(walk) vs the cursor prototype.

The sweep compares anchors. This oracle compares what a user receives from
``Tree.find`` — rows, order, field values, and the raised error class. It
covers the named dimensions: root and nested matches, repeated matches,
ancestor context, field and named-node constraints, row ordering, missing
optional nodes, malformed queries, and the raw-query escape hatch.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness  # noqa: E402
from oracle_sweep import row_summary  # noqa: E402

from pydantree_sitter.find import find_in  # noqa: E402

LANGUAGES = ("python", "bash", "nix", "rust", "markdown")


def outcome(fn):
    """Run a find and record either rows or the raised error class."""
    try:
        rows = fn()
    except Exception as error:  # noqa: BLE001 - the oracle records errors
        return {"error": type(error).__name__,
                "detail": str(error).splitlines()[0][:200]}
    return {"rows": row_summary(rows)}


def compare(language, tier, case, cls, raw, ts_language):
    a = outcome(lambda: find_in(raw, cls, ts_language))     # shipped default
    b = outcome(lambda: find_in(raw, cls, None))            # shipped fallback
    c = outcome(lambda: harness.find_in_cursor(raw, cls, ts_language))
    rec = {"language": language, "tier": tier, "case": case,
           "kind": getattr(cls, "__kind__", None),
           "query_vs_walk": "same" if a == b else "DIFFER",
           "cursor_vs_walk": "same" if c == b else "DIFFER",
           "cursor_vs_query": "same" if c == a else "DIFFER",
           "n_query": len(a.get("rows", [])) if "rows" in a else None,
           "n_walk": len(b.get("rows", [])) if "rows" in b else None,
           "n_cursor": len(c.get("rows", [])) if "rows" in c else None,
           "err_query": a.get("error"), "err_walk": b.get("error"),
           "err_cursor": c.get("error")}
    if a != b and "rows" in a and "rows" in b:
        sa = [r["span"] for r in a["rows"]]
        sb = [r["span"] for r in b["rows"]]
        rec["order_only"] = sorted(sa) == sorted(sb)
        rec["missing_from_query"] = [s for s in sb if s not in sa][:3]
        rec["extra_in_query"] = [s for s in sa if s not in sb][:3]
    return rec


def narrow(base, name, annotations=None, under=None, raw=None, kind=None):
    """Build a Node subclass from real annotation objects.

    The probe module uses ``from __future__ import annotations``, so a class
    body would hand the metaclass unresolvable strings. Real objects in
    ``__annotations__`` keep the declaration honest.
    """
    body: dict = {}
    if kind is not None:
        body["__kind__"] = kind
    if under is not None:
        body["__under__"] = under
    if raw is not None:
        body["__raw_query__"] = raw
    body["__annotations__"] = dict(annotations or {})
    return type(name, (base,), body)


def build_cases(language, ns):
    """Return (case_name, class) pairs exercising the named dimensions."""
    from pydantree_sitter import Node
    from pydantree_sitter.raw import RawQuery

    cases: list[tuple[str, type]] = []

    def add(name, cls):
        cases.append((name, cls))

    if language == "python":
        add("root/module", ns.Module)
        add("plain/function_definition", ns.FunctionDefinition)
        add("plain/assignment", ns.Assignment)
        add("field-narrowed/function_definition.name", narrow(
            ns.FunctionDefinition, "NamedFunc", {"name": ns.Identifier}))
        add("optional-missing/function_definition.return_type", narrow(
            ns.FunctionDefinition, "OptionalReturn",
            {"return_type": ns.Type | None}))
        add("optional-missing/assignment.type", narrow(
            ns.Assignment, "OptionalType", {"type": ns.Type | None}))
        add("field-narrowed/assignment.left", narrow(
            ns.Assignment, "LeftPattern", {"left": ns.PatternList | None}
            if False else {"left": ns.Pattern | ns.PatternList}))
        add("scalar-field/function_definition.name", narrow(
            ns.FunctionDefinition, "ScalarName", {"name": str}))
        add("repeated/module.content-functions", narrow(
            ns.Module, "RepeatedFuncs",
            {"content": list[ns.FunctionDefinition]}))
        add("ancestor/function_definition-under-module", narrow(
            ns.FunctionDefinition, "UnderModule", under=(
                ns.Module, ns.FunctionDefinition)))
        add("raw-query/function-names", narrow(
            Node, "RawIdent", {"name": str}, kind="identifier",
            raw=RawQuery("(function_definition name: (identifier) @name)")))
        add("malformed-raw-query", narrow(
            Node, "BadRaw", {"name": str}, kind="identifier",
            raw=RawQuery("(function_definition name: (nonexistent) @name)")))
        add("raw-query-unknown-capture", narrow(
            Node, "UnknownCap", {"name": str}, kind="identifier",
            raw=RawQuery("(function_definition name: (identifier) @other)")))

    elif language == "bash":
        add("root/program", ns.Program)
        add("plain/function_definition", ns.FunctionDefinition)
        add("plain/variable_assignment", ns.VariableAssignment)
        add("plain/command", ns.Command)
        add("nested/unary_expression", ns.UnaryExpression)
        add("nested/binary_expression", ns.BinaryExpression)
        add("ancestor/function-under-program", narrow(
            ns.FunctionDefinition, "UnderProgram", under=(
                ns.Program, ns.FunctionDefinition)))
        add("field-narrowed/command.name", narrow(
            ns.Command, "CmdName", {"name": ns.CommandName}))

    elif language == "nix":
        add("root/source_expression", getattr(ns, "SourceExpression",
                                              ns.Binding))
        add("plain/binding", ns.Binding)
        add("nested/apply_expression", ns.ApplyExpression)
        add("nested/select_expression", ns.SelectExpression)
        add("plain/attrset_expression", ns.AttrsetExpression)
        add("ancestor/binding-under-attrset", narrow(
            ns.Binding, "UnderAttrset", under=(
                ns.AttrsetExpression, ns.Binding)))

    elif language == "rust":
        add("root/source_file", ns.SourceFile)
        add("plain/function_item", ns.FunctionItem)
        add("plain/let_declaration", ns.LetDeclaration)
        add("nested/scoped_identifier", ns.ScopedIdentifier)
        add("nested/binary_expression", ns.BinaryExpression)
        add("plain/impl_item", ns.ImplItem)
        add("field-narrowed/function_item.name", narrow(
            ns.FunctionItem, "FnNamed", {"name": ns.Identifier}))
        add("ancestor/function-under-impl", narrow(
            ns.FunctionItem, "UnderImpl", under=(
                ns.ImplItem, ns.DeclarationList, ns.FunctionItem)))

    elif language == "markdown":
        add("root/document", ns.Document)
        add("plain/atx_heading", ns.AtxHeading)
        add("plain/fenced_code_block", ns.FencedCodeBlock)
        add("plain/list", ns.List)
        add("repeated/list-items", ns.ListItem)
        add("ancestor/heading-under-section", narrow(
            ns.AtxHeading, "UnderSection", under=(ns.Section, ns.AtxHeading)))

    return cases


def run() -> dict:
    out = {"cases": [], "errors": []}
    for language in LANGUAGES:
        grammar = harness.grammar(language)
        try:
            cases = build_cases(language, grammar.nodes)
        except Exception:
            out["errors"].append({"language": language, "where": "build_cases",
                                  "traceback": traceback.format_exc()})
            continue
        for cf in harness.corpus_files():
            if cf.language != language:
                continue
            raw = grammar.parse(cf.text).root_node
            for case, cls in cases:
                try:
                    out["cases"].append(
                        compare(language, cf.tier, case, cls, raw,
                                grammar.language))
                except Exception:
                    out["errors"].append({
                        "language": language, "tier": cf.tier, "case": case,
                        "traceback": traceback.format_exc().splitlines()[-4:]})
    return out


if __name__ == "__main__":
    result = run()
    qd = [c for c in result["cases"] if c["query_vs_walk"] == "DIFFER"]
    cd = [c for c in result["cases"] if c["cursor_vs_walk"] == "DIFFER"]
    cq = [c for c in result["cases"] if c["cursor_vs_query"] == "DIFFER"]
    print(f"cases={len(result['cases'])} "
          f"query_vs_walk_DIFFER={len(qd)} "
          f"cursor_vs_walk_DIFFER={len(cd)} "
          f"cursor_vs_query_DIFFER={len(cq)} errors={len(result['errors'])}",
          file=sys.stderr)
    for c in cq:
        print(f"  CURSOR!=QUERY {c['language']:9s} {c['tier']:6s} "
              f"{c['case']:44s} c={c['n_cursor']} q={c['n_query']} "
              f"errc={c['err_cursor']} errq={c['err_query']}", file=sys.stderr)
    for c in qd:
        print(f"  QUERY!=WALK {c['language']:9s} {c['tier']:6s} {c['case']:44s} "
              f"q={c['n_query']} w={c['n_walk']} "
              f"order_only={c.get('order_only')} "
              f"errq={c['err_query']} errw={c['err_walk']}", file=sys.stderr)
    for c in cd:
        print(f"  CURSOR!=WALK {c['language']:9s} {c['tier']:6s} {c['case']:44s} "
              f"c={c['n_cursor']} w={c['n_walk']} "
              f"errc={c['err_cursor']} errw={c['err_walk']}", file=sys.stderr)
    for e in result["errors"]:
        print("  ERROR", json.dumps(e)[:400], file=sys.stderr)
    json.dump(result, sys.stdout, indent=1)
