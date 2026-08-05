#!/usr/bin/env python3
"""
Phase 5 — the reach experiment (polish & reach: corpus + distribution).

  RUN 1 — the corpus harness bite (B). The qfilter corpus (expression shapes
          in the compact smoke style + statement shapes in the sexp style)
          passes on the known-good grammar; three planted regressions that
          GENERATE CLEAN but parse wrongly (ladder reorder, associativity
          flip, postfix-below-unary) are caught at author time, plus a
          statement-level structural regression (the latent qfilter block bug
          the corpus authoring found). Metrics: which of the three the smoke
          seed already catches vs the full corpus, the author effort, and the
          diff reviewability.

  RUN 2 — the artifact seam in production (B -> pydantree_sitter -> A). The cfg grammar
          is packaged (BuildResult.package) into a bundle; a SEPARATE process
          where pydantree_sitter_grammar is NOT importable consumes it via
          Language.load_bundle with the Phase-4 ground truth passing and the
          checks active. The community path: the schema tool derives
          node-schema.json from the json grammar's node-types.json (agreeing
          with derive_from_ir), and a B-free process binds it to the
          tree_sitter_json wheel and extracts the Phase-1 Person ground truth.
          Metrics: bundle file list + sizes, loader line count, the
          byte-identical A surface with and without B.

  RUN 3 — the honest control. The same consumption task through raw
          py-tree-sitter: ctypes-load the bundle .so, no schema, hand-rolled
          .scm + dispatch. Author effort and where mistakes surface.

Raw outputs are saved verbatim under evidence/.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Annotated

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / ".scratch" / "006-query-bridge"))
sys.path.insert(0, str(ROOT / ".scratch" / "005-grammar-glr"))
sys.path.insert(0, str(ROOT / ".scratch" / "007-query-distribution"))

import tree_sitter_json  # noqa: E402
import pydantree_sitter_grammar as tg  # noqa: E402

from bfree import run_bfree  # noqa: E402
from cfg_grammar import (  # noqa: E402
    CORPUS,
    LISTEN_GROUND_TRUTH,
    SECTION_GROUND_TRUTH,
    build as build_cfg,
)
from json_grammar import build as build_json  # noqa: E402
from qfilter_corpus import EXPR_CASES, STMT_CASES, expression_corpus, statement_corpus  # noqa: E402
from pydantree_sitter.schema import NodeSchema, derive_from_ir  # noqa: E402
from pydantree_sitter_grammar.language import load_language  # noqa: E402
from pydantree_sitter import (  # noqa: E402
    Language,
    M,
    OutputModel,
    SchemaCheckError,
    capture,
    source_meta,
)

EVIDENCE = Path(__file__).parent / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)


def banner(t: str, width: int = 76) -> None:
    print("\n" + "=" * width + f"\n{t}\n" + "=" * width)


def save(name: str, text: str) -> None:
    (EVIDENCE / name).write_text(text)
    print(f"  [evidence saved] {EVIDENCE / name}")


# ---------------------------------------------------------------------------
# RUN 1 — the corpus harness bite
# ---------------------------------------------------------------------------

GOOD_LADDER = ("or", "and", "not", "compare", "add", "mul", "unary", "pow",
               "postfix")


def _expr_grammar(name, *, ladder=GOOD_LADDER, plus_assoc="left") -> tg.Grammar:
    """A qfilter-shaped expression grammar (the corpus's subject). `ladder`
    is the declarative ordering; `plus_assoc` flips `+` associativity — the
    two levers the planted regressions pull."""
    g = tg.Grammar(name)
    g.rule("number", tg.pattern(r"\d+(\.\d+)?"))
    g.rule("identifier", tg.pattern(r"[a-zA-Z_][a-zA-Z0-9_]*"), word=True)
    g.rule("args", tg.seq(tg.ref("expr"), tg.repeat(tg.seq(",", tg.ref("expr")))))
    prec = g.precedence(*ladder)
    tg.expression(g, "expr",
                  primary=tg.choice(tg.ref("number"), tg.ref("identifier"),
                                    tg.seq("(", tg.ref("expr"), ")")),
                  infix=[("or", "left", "or"), ("and", "left", "and"),
                         ("<", "left", "compare"), ("==", "left", "compare"),
                         ("+", plus_assoc, "add"), ("*", "left", "mul"),
                         ("^", "right", "pow")],
                  prefix=[("-", "unary"), ("not", "not")],
                  postfix=[
                      ("call", "postfix",
                       lambda e: tg.seq(e, "(", tg.opt(tg.ref("args")), ")")),
                      ("member", "postfix",
                       lambda e: tg.seq(e, ".", tg.ref("identifier"))),
                  ],
                  ladder=prec)
    g.rule("stmt", tg.seq(tg.ref("expr"), ";"))
    g.rule("source_file", tg.repeat(tg.ref("stmt")))
    g.start("source_file")
    return g


def run1() -> None:
    banner("RUN 1 — the corpus harness bite (B): generate-clean regressions "
           "caught at author time")
    from pydantree_sitter_grammar.expressions import semantic_smoke
    import qfilter

    # -- the known-good corpus ----------------------------------------------
    g = qfilter.build()
    issues = list(tg.run_checks(g))
    assert not tg.errors(g), issues
    res = tg.build_builder(g)
    rexpr = expression_corpus().run(build_result=res)
    rstmt = statement_corpus().run(build_result=res)
    print(f"1.1 qfilter ({len(g.rules)} rules): expression corpus "
          f"{len(rexpr.cases)} case(s) — {'PASS' if rexpr.ok() else 'FAIL'}; "
          f"statement corpus {len(rstmt.cases)} case(s) — "
          f"{'PASS' if rstmt.ok() else 'FAIL'}")
    save("r1_qfilter_expr.txt", rexpr.report())
    save("r1_qfilter_stmt.txt", rstmt.report())

    # author effort: the corpus lines
    src = (Path(__file__).parent / "qfilter_corpus.py").read_text()
    case_lines = sum(1 for line in src.splitlines()
                     if line.strip().startswith("corpus_case("))
    print(f"1.2 author effort: {case_lines} corpus_case() lines ("
          f"{len(EXPR_CASES) + len(STMT_CASES)} cases) for a "
          f"{len(g.rules)}-rule grammar")

    # -- the planted regressions --------------------------------------------
    regressions = [
        ("R1 ladder reorder (unary ABOVE pow)",
         _expr_grammar("r1", ladder=("or", "and", "not", "compare", "add",
                                     "mul", "pow", "unary", "postfix")),
         {"'-a ^ b;'", "'-a ^ b;'"},
         "smoke seed catches it too (`-a ^ b` is in the seed)"),
        ("R2 associativity flip (+ right-assoc)",
         _expr_grammar("r2", plus_assoc="right"),
         {"'1 + 2 + 3;'"},
         "smoke seed is BLIND to it (no chain case in the seed)"),
        ("R3 postfix below unary",
         _expr_grammar("r3", ladder=("or", "and", "not", "compare", "add",
                                     "mul", "postfix", "unary", "pow")),
         {"'-f(x);'", "'-a.b;'", "'-f(x) + 1;'"},
         "smoke seed catches `-f(x)`; the corpus adds `-a.b`, `-f(x) + 1`"),
    ]
    out = ["RUN 1 — planted regressions (all GENERATE CLEAN, parse wrongly)\n"]
    for label, gx, expect_sub, note in regressions:
        result = tg.build_builder(gx)          # clean generate or it would raise
        r = expression_corpus().run(build_result=result)
        smoke = semantic_smoke(gx)
        caught = [f.case.source for f in r.failures]
        missing = expect_sub - {f"'{c}'" for c in caught}
        status = "CATCH" if not missing else f"MISS {sorted(missing)}"
        print(f"  1.3 {label}: generate clean, corpus {status} — {note}")
        for f in r.failures:
            print(f"        {f.case.source!r}: got {f.got!r}")
        out.append(f"{label}: {status} ({note})")
        out.append(f"  smoke-seed failures: {len(smoke)}")
        out.append(f"  full-corpus failures: {len(r.failures)}")
        for f in r.failures:
            out.append(f"    {f.case.source!r} -> {f.got!r}")
    save("r1_planted_regressions.txt", "\n".join(out))

    # -- the statement-level regression (the latent qfilter bug) ------------
    from pydantree_sitter_grammar.ir import ChoiceNode, SymbolNode
    gb = qfilter.build()
    stmt: ChoiceNode = gb.rules["statement"]
    gb.rules["statement"] = ChoiceNode(members=[
        m for m in stmt.members
        if not (isinstance(m, SymbolNode) and m.name == "block")])
    res_b = tg.build_builder(gb)              # clean generate (it shipped!)
    rb = statement_corpus().run(build_result=res_b)
    print(f"1.4 statement-level regression (block dropped from the statement "
          f"supertype — the latent bug the corpus authoring FOUND in the "
          f"Phase-3 fixture): generates clean, statement corpus "
          f"{'CATCHES ' + str(len(rb.failures)) + ' case(s)' if not rb.ok() else 'MISSES it'}")
    save("r1_statement_regression.txt", rb.report())

    # -- diff reviewability -------------------------------------------------
    gx = _expr_grammar("r2", plus_assoc="right")
    result = tg.build_builder(gx)
    r = expression_corpus().run(build_result=result)
    sample = [line for line in r.report().splitlines() if line.startswith("      ")]
    print("  1.5 diff reviewability (a failure's unified diff):")
    print("      " + "\n      ".join(sample[:5]))
    save("r1_diff_sample.txt", r.report())
    # snapshots for reviewable grammar diffs
    import shutil as _shutil
    snap = EVIDENCE / "r1_snapshots"
    snap.mkdir(exist_ok=True)
    _shutil.copyfile(res.grammar_json, snap / "grammar.json")
    _shutil.copyfile(res.node_schema_json, snap / "node-schema.json")
    print(f"  1.6 snapshots: {snap / 'grammar.json'}, {snap / 'node-schema.json'}")


# ---------------------------------------------------------------------------
# RUN 2 — the artifact seam in production (B-free subprocess)
# ---------------------------------------------------------------------------

def run2() -> None:
    banner("RUN 2 — the artifact seam in production (B -> pydantree_sitter -> A, "
           "B-free subprocess)")
    work = Path(tempfile.mkdtemp(prefix="phase5-run2-"))

    # -- the bundle ----------------------------------------------------------
    g = build_cfg()
    result = tg.build_builder(g)
    bundle = result.package(work / "bundle")
    files = {p.name: p.stat().st_size for p in bundle.iterdir()}
    loader_lines = len((bundle / "loader.py").read_text().splitlines())
    print("2.1 bundle:", files, f"(loader.py = {loader_lines} lines)")
    save("r2_bundle_manifest.txt",
         "\n".join(f"{k}: {v} bytes" for k, v in sorted(files.items()))
         + f"\nloader.py lines: {loader_lines}")

    # -- the B-free consumer -------------------------------------------------
    rc, out = run_bfree(Path(__file__).parent / "consumer.py", str(bundle),
                        workdir=work)
    data = json.loads(out)
    ok = rc == 0 and data["ok"]
    print(f"2.2 B-free subprocess consumer (pydantree_sitter_grammar NOT importable): "
          f"{'PASS' if ok else 'FAIL'} — record + field ground truth, "
          f"checks active (schema_bound={data['schema_bound']})")
    print("    sections:", data["sections"])
    save("r2_bfree_consumer.txt",
         f"exit={rc}\n" + json.dumps(data, indent=2))

    # -- byte-identical surface with/without B -------------------------------
    lang, _ = result.language()
    bound = Language.load(lang, schema=result.node_schema())

    class ServerSection(OutputModel):
        __match__ = M("source_file", "section", record=True)
        host: str
        port: int
        debug: bool = False
        title: str | None = None
        line: int = source_meta()

    inproc = [r.model_dump() for r in ServerSection.extract(CORPUS, language=bound)]
    same = inproc == data["sections"] == SECTION_GROUND_TRUTH
    print(f"2.3 A surface byte-identical in-process vs B-free: "
          f"{'PASS' if same else 'FAIL'}")
    save("r2_byte_identical.txt",
         f"in-process == B-free == ground truth: {same}\n{inproc}")

    # -- the community path --------------------------------------------------
    from pydantree_sitter_grammar.schema_tool import derive_schema_for_dir
    json_model = build_json().build()
    src_dir = work / "json_grammar"
    json_model.emit_bundle(src_dir)
    derived = derive_schema_for_dir(src_dir, name="json",
                                    workdir=work / "cw",
                                    out=work / "cw" / "node-schema.json",
                                    keep=True)
    from_ir = NodeSchema.from_list(derive_from_ir(json_model), name="json")
    agree = derived.to_json() == from_ir.to_json()
    print(f"2.4 community-schema tool over the json grammar: "
          f"{len(derived.node_types)} kinds, agreement with derive_from_ir: "
          f"{'PASS' if agree else 'FAIL'}")
    rc2, out2 = run_bfree(Path(__file__).parent / "consumer_community.py",
                          str(work / "cw" / "node-schema.json"), workdir=work)
    data2 = json.loads(out2)
    ok2 = rc2 == 0 and data2["ok"]
    print(f"2.5 community path, B-free over the tree_sitter_json wheel: "
          f"{'PASS' if ok2 else 'FAIL'} (Person ground truth, checks active)")
    save("r2_community.txt",
         f"agreement={agree}\nexit={rc2}\n" + json.dumps(data2, indent=2))
    assert ok and same and agree and ok2


# ---------------------------------------------------------------------------
# RUN 3 — the honest control: raw py-tree-sitter, no schema
# ---------------------------------------------------------------------------

def run3() -> None:
    banner("RUN 3 — the honest control: raw py-tree-sitter over the same "
           "bundle .so, no schema")
    work = Path(tempfile.mkdtemp(prefix="phase5-run3-"))
    g = build_cfg()
    result = tg.build_builder(g)
    bundle = result.package(work / "bundle")

    # the raw path: ctypes -> PyCapsule -> tree_sitter.Language, hand-rolled
    # .scm + manual dispatch + manual coercion — no pydantree_sitter, no schema
    import ctypes
    import tree_sitter
    lib = ctypes.CDLL(str(bundle / "grammar.so"))
    fn = getattr(lib, "tree_sitter_cfg")
    fn.restype = ctypes.c_void_p
    _pycapsule_new = ctypes.pythonapi.PyCapsule_New
    _pycapsule_new.restype = ctypes.py_object
    _pycapsule_new.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
    lang = tree_sitter.Language(
        _pycapsule_new(fn(), b"tree_sitter.Language", None))

    RAW_SCM = """\
(source_file (section (entry key: (identifier) @key value: (_) @val)) @rec)
(source_file (directive name: (directive_name) @name arg: (_) @arg) @dir)
"""

    # NOTE: (a) `(value)` — the grammar's supertype — matches NOTHING in a
    # query (supertypes never appear in the CST); the raw author must write a
    # wildcard or enumerate the subtypes by hand. (b) a capture binds to the
    # node whose `)` it follows, so `@dir` must sit on the directive, not the
    # source_file — both bits of grammar/binding knowledge the schema + DSL
    # derivation provide for free.

    q = tree_sitter.Query(lang, RAW_SCM)
    tree = tree_sitter.Parser(lang).parse(CORPUS.encode())
    records, directives = [], []
    seen_records: set = set()
    for _pi, caps in tree_sitter.QueryCursor(q).matches(tree.root_node):
        if "rec" in caps:
            rec = caps["rec"][0]
            if rec.id in seen_records:
                continue  # anchored patterns re-match per inner entry — dedup
            seen_records.add(rec.id)
            row = {"host": None, "port": None, "debug": False, "title": None,
                   "line": rec.start_point.row + 1}
            # manual dispatch: run the field query scoped to the record
            fld = tree_sitter.Query(lang, (
                "(entry key: (identifier) @key value: (_) @val)"))
            for _fpi, fc in tree_sitter.QueryCursor(fld).matches(rec):
                key = fc["key"][0].text.decode()
                raw = fc["val"][0].text.decode()
                if key == "host":
                    row["host"] = raw
                elif key == "port":
                    row["port"] = int(raw)          # manual coercion
                elif key == "debug":
                    row["debug"] = raw == "true"    # manual coercion
                elif key == "title":
                    row["title"] = raw.strip('"')   # manual unquoting
            records.append(row)
        elif "dir" in caps:
            node = caps["dir"][0]
            name = caps["name"][0].text.decode()
            raw = caps["arg"][0].text.decode()
            try:
                port = int(raw)                      # manual coercion
                directives.append({"name": name, "port": port,
                                   "line": node.start_point.row + 1})
            except ValueError:
                pass  # include \"base.conf\" — silently filtered by hand

    ok_r = records == SECTION_GROUND_TRUTH
    ok_d = directives == LISTEN_GROUND_TRUTH
    print(f"3.1 raw control rows vs ground truth: records "
          f"{'PASS' if ok_r else 'FAIL'}, directives "
          f"{'PASS' if ok_d else 'FAIL'}")
    control = f"""RUN 3 — the raw py-tree-sitter control (no schema)

  raw surface: ctypes/PyCapsule load + 2 hand-written .scm patterns + a
  manual dispatch table (key -> field) + manual int/bool coercion + manual
  string unquoting + a try/except for non-numeric args.

  author effort (this task):
    .scm patterns:         2 lines (value supertype = one wildcard-ish shape)
    dispatch table:        ~10 lines (key -> field, per-key coercion)
    coercion:              int() / == "true" / strip('"') by hand
    schema (none):         NO model/grammar check, NO shape derivation, NO
                           capture/type check, NO record-level anchoring,
                           NO descendant matching, NO unescaping

  where mistakes surface (this task):
    kind/field typo in .scm      -> Query() construction error (free)
    capture can't coerce (port)  -> silent row filter (the try/except) or a
                                    runtime crash mid-loop
    wrong value shape            -> silent wrong row (no schema to restrict
                                    the value supertype)
    nested key collision         -> AmbiguousCapture-equivalent runtime bug
    chain/descent error          -> silent empty result
    no unescaping                -> title keeps the quotes unless hand-stripped

  comparison (same two tasks):

    metric                  raw control          Phase 5 (bundle + schema)
    --------------------    ----------------     ---------------------------
    loading                 ctypes boilerplate   Language.load_bundle(dir)
                            (4 lines)            (1 call)
    query                   hand-written .scm    model-only (derived .scm)
    value shapes            value supertype      derived per type
                            (hand-written)       (0 hand-written lines)
    coercion                manual int/bool     pydantic (lax, typed)
    string unquoting        manual strip('"')    Unescaped() + json decode
    kind/type mistakes      silent wrong row     validate_with (schema cited)
    chain/descent mistakes  silent empty result  validate_with (Job 1)
    checks before parsing   none                 Jobs 1/3/4 at validate_with
    author effort (task)    ~20 lines            ~10 model lines
"""
    save("r3_control.txt", control)
    print(control)


def main() -> None:
    run1()
    run2()
    run3()
    banner("DONE — Phase-5 experiment complete (verdict in FINDINGS.md)")


if __name__ == "__main__":
    main()
