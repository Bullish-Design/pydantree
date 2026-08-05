"""Phase 0 — oracles: freeze observable extraction behavior on real inputs.

For each of the three `examples/` (bash-extract, devenv-extract,
devenv-subset), run the example's extraction end-to-end — its OWN models and
helpers over its OWN corpus, with a `Language` built from the vendored
grammar-source fixtures (`tests/fixtures/{bash,nix}`; the devenv-subset
grammar authored in the example dir itself) — and assert against the
checked-in expected-output JSON in `tests/oracles/`. These files are the
contract across the whole refactor: the Phase 4 Product-A rewrite (and the
Phase 6 B pass) must not change observable extraction behavior on these
inputs.

Also pins the CORRECT behavior for the review's thesis-breaking bugs; each
fails on the current code and is marked `xfail(strict=True)` with the
finding ID, flipping to a plain test at its phase:

  - F-A1       cross-language silent `[]` (dsl.py compile cache ignores lang)
  - F-A2       schema-bound nested records drop every nested match
  - F-A3       NodeKind tuple alternation dropped in field mode
  - NEW        list[T] + `...` path: the ancestor filter is skipped
  - T-1        choice-order `required` diverges from the CLI (killed in Ph 3)

Regenerate the oracle JSONs from current code (one-time, then eyeball):

    devenv shell -- python tests/test_oracles.py --generate
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
ORACLES = TESTS / "oracles"
EXAMPLES = REPO / "examples"
BASH_FIXTURE = TESTS / "fixtures" / "bash"
NIX_FIXTURE = TESTS / "fixtures" / "nix"

TOOLCHAIN_AVAILABLE = shutil.which("tree-sitter") is not None and \
    shutil.which("gcc") is not None
requires_toolchain = pytest.mark.skipif(
    not TOOLCHAIN_AVAILABLE, reason="tree-sitter CLI / gcc not on PATH")

BASH_FILES = ("sample.sh", "real_script.sh", "unclosed.sh")


# ---------------------------------------------------------------------------
# example-module loading (importlib: the examples are scripts, not packages)
# ---------------------------------------------------------------------------

def _import_example(name: str):
    mod_name = f"oracle_example_{name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(
        mod_name, EXAMPLES / name / "extract.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Languages (session-scoped: build each bundle once per test session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def bash_lang():
    from tsgrammar.schema_tool import build_community_bundle
    from tsquery import Language
    bundle = build_community_bundle(BASH_FIXTURE, ORACLES / ".built" / "bash",
                                    name="bash", keep=False)
    return Language.load_bundle(bundle)


@pytest.fixture(scope="session")
def nix_lang():
    from tsgrammar.schema_tool import build_community_bundle
    from tsquery import Language
    bundle = build_community_bundle(NIX_FIXTURE, ORACLES / ".built" / "nix",
                                    name="nix", keep=False)
    return Language.load_bundle(bundle)


def build_subset_bundle(mod, out_dir: Path):
    """The devenv-subset bundle: the example's OWN grammar.py + scanner.c,
    built through B exactly as the example's main() does (its build_bundle
    hardcodes DIST; ours lands in out_dir), consumed with
    Language.load_bundle."""
    import sys as _sys
    import tsgrammar as tg

    _sys.path.insert(0, str(EXAMPLES / "devenv-subset"))
    from grammar import build

    g = build()
    warnings = list(tg.run_checks(g))
    assert not tg.errors(g), warnings
    result = tg.build_builder(
        g, scanner=str(EXAMPLES / "devenv-subset" / "scanner.c"))
    return result.package(out_dir)


@pytest.fixture(scope="session")
def subset_lang():
    from tsquery import Language
    example = _import_example("devenv-subset")
    bundle = build_subset_bundle(example, ORACLES / ".built" / "subset")
    return Language.load_bundle(bundle)


# ---------------------------------------------------------------------------
# collectors — the example's own extraction, driven the way main() drives it
# ---------------------------------------------------------------------------

def collect_bash(mod, lang) -> dict:
    out = {}
    for fname in BASH_FILES:
        src = (EXAMPLES / "bash-extract" / fname).read_text()
        out[fname] = {
            "functions": [r.model_dump() for r in
                          mod.FunctionDef.extract(src, language=lang)],
            "assignments": [r.model_dump() for r in
                            mod.Assignment.extract(src, language=lang)],
            "heredocs": [r.model_dump() for r in
                         mod.Heredoc.extract(src, language=lang)],
        }
    return out


def collect_nix(mod, lang) -> dict:
    inventory = {"packages": [], "env": [], "scripts": [], "tasks": [],
                 "switches": [], "enterShell": [], "enterTest": []}
    for fname in mod.FILES:
        repo = fname[:-4]
        src = (mod.FLEET / fname).read_bytes()
        tree = lang.parse(src)

        model_rows = [r.model_dump() for r in mod.Binding.extract_tree(tree)]
        bindings = mod.walk(tree.root_node, "binding")
        assert len(model_rows) == len(bindings), fname
        for model_row, node in zip(model_rows, bindings):
            value = model_row["value"]
            path = mod.dotted_path(node, src)
            line = mod.line_at(src, node.start_byte)
            kind = mod.classify(path, value)
            if kind == "env":
                inventory["env"].append({"repo": repo, "name": path,
                                         "value": value, "line": line})
            elif kind == "script":
                inventory["scripts"].append({"repo": repo, "name": path,
                                             "body": value, "line": line})
            elif kind == "task":
                inventory["tasks"].append({"repo": repo, "name": path,
                                           "body": value, "line": line})
            elif kind == "switch":
                inventory["switches"].append({"repo": repo, "path": path,
                                              "line": line})
            elif kind == "shell":
                inventory["enterShell"].append(
                    {"repo": repo, "kind": "enterShell", "body": value,
                     "line": line})
            elif kind == "test":
                inventory["enterTest"].append(
                    {"repo": repo, "kind": "enterTest", "body": value,
                     "line": line})

        for lst in mod.walk(tree.root_node, "list_expression"):
            if not mod.is_packages_list(lst, src):
                continue
            for el in mod.element_rows(lst, src):
                inventory["packages"].append(
                    {"repo": repo, "name": el["name"], "line": el["line"]})
    return inventory


def collect_subset(mod, lang) -> dict:
    inventory = {"packages": [], "env": [], "scripts": [], "tasks": [],
                 "switches": [], "enterShell": [], "enterTest": []}
    env_records, toolchain_records = [], []
    for fname in mod.FILES:
        repo = fname[:-4]
        src = (mod.FIXTURES / fname).read_bytes()
        tree = lang.parse(src)

        pairs = [r.model_dump() for r in mod.Pair.extract_tree(tree)]
        for row in pairs:
            node = mod.node_at(tree, row["span"])
            assert node is not None and node.type == "pair", fname
            value, path = row["value"], mod.dotted_path(node, src)
            line = row["line"]
            kind = mod.classify(path, value)
            if kind == "env":
                inventory["env"].append({"repo": repo, "name": path,
                                         "value": value, "line": line})
            elif kind == "script":
                inventory["scripts"].append({"repo": repo, "name": path,
                                             "body": value, "line": line})
            elif kind == "task":
                inventory["tasks"].append({"repo": repo, "name": path,
                                           "body": value, "line": line})
            elif kind == "switch":
                inventory["switches"].append({"repo": repo, "path": path,
                                              "line": line})
            elif kind == "shell":
                inventory["enterShell"].append(
                    {"repo": repo, "kind": "enterShell", "body": value,
                     "line": line})
            elif kind == "test":
                inventory["enterTest"].append(
                    {"repo": repo, "kind": "enterTest", "body": value,
                     "line": line})

        for lst_row in [r.model_dump() for r in mod.ListLiteral.extract_tree(tree)]:
            node = mod.node_at(tree, lst_row["span"])
            if not mod.is_packages_list(node, src):
                continue
            for i in range(node.child_count):
                c = node.children[i]
                if node.field_name_for_child(i) == "element":
                    inventory["packages"].append(
                        {"repo": repo,
                         "name": src[c.start_byte:c.end_byte].decode(),
                         "line": c.start_point.row + 1})

        for r in [x.model_dump() for x in
                  mod.EnvRecord.extract_tree(tree, strict=False,
                                             schema=lang.schema)]:
            r["repo"] = repo
            env_records.append(r)
        for r in [x.model_dump() for x in
                  mod.Toolchain.extract_tree(tree, strict=False,
                                             schema=lang.schema)]:
            r["repo"] = repo
            toolchain_records.append(r)

    inventory["env_records"] = env_records
    inventory["toolchain_records"] = toolchain_records
    return inventory


# ---------------------------------------------------------------------------
# the oracle tests
# ---------------------------------------------------------------------------

def _oracle(name: str) -> dict:
    return json.loads((ORACLES / f"{name}.json").read_text())


@requires_toolchain
def test_bash_extract_matches_oracle(bash_lang):
    mod = _import_example("bash-extract")
    assert collect_bash(mod, bash_lang) == _oracle("bash-extract")


@requires_toolchain
def test_devenv_extract_matches_oracle(nix_lang):
    mod = _import_example("devenv-extract")
    assert collect_nix(mod, nix_lang) == _oracle("devenv-extract")


@requires_toolchain
def test_devenv_subset_matches_oracle(subset_lang):
    mod = _import_example("devenv-subset")
    assert collect_subset(mod, subset_lang) == _oracle("devenv-subset")


@requires_toolchain
def test_oracles_agree_with_the_examples_own_ground_truth():
    """The oracle JSONs are generated from current code; the examples'
    hand-written ground truths are the pre-model spec. They must agree
    (modulo provenance notes) — otherwise the oracle froze a drift."""
    for name, truth_path in (
        ("bash-extract", EXAMPLES / "bash-extract" / "ground_truth.json"),
        ("devenv-extract", EXAMPLES / "devenv-extract" / "fleet"
         / "ground_truth.json"),
        ("devenv-subset", EXAMPLES / "devenv-subset" / "ground_truth.json"),
    ):
        truth = json.loads(truth_path.read_text())
        truth.pop("note", None)
        truth.pop("_note", None)
        oracle = _oracle(name)
        assert oracle == truth, (
            f"oracle {name}.json drifted from the example's hand truth — "
            f"regenerate + eyeball")


# ---------------------------------------------------------------------------
# thesis-breaking bugs pinned as xfails (flip in Phase 3 / Phase 4)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="F-A1: silent [] (dsl compile cache "
                                       "ignores lang) — flip in Phase 4")
def test_fa1_cross_language_second_extract_raises():
    """F-A1: a model extracted against python then json must RAISE on the
    second language (the query is grammar-specific), never silently return
    []. Current bug: the class-level _derived_cache + Query._compiled ignore
    the second language. Fix in Phase 4.2 (binding owns compiled state)."""
    import tree_sitter_json
    import tree_sitter_python
    from tsquery import Language, M, OutputModel, QueryBuildError, capture

    class PyAssignment2(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        left: str = capture("left")
        right: str = capture("right")

    py = Language.load(tree_sitter_python.language())
    js = Language.load(tree_sitter_json.language())

    assert PyAssignment2.extract("x = 1", language=py)[0].left == "x"
    with pytest.raises(QueryBuildError):
        PyAssignment2.extract('{"a": 1}', language=js)


@pytest.mark.xfail(strict=True, reason="F-A2: schema-bound nested records "
                                       "drop every nested match — Phase 4.4")
def test_fa2_schema_bound_nested_records_match_schema_less():
    import sys as _sys
    import tree_sitter_json
    from tsquery import Language, M, OutputModel

    _sys.path.insert(0, str(REPO / ".scratch" / "projects" / "006-tsquery-bridge"))
    from json_grammar import build as build_json
    from tscore.schema import NodeSchema, derive_from_ir

    schema = NodeSchema.from_list(derive_from_ir(build_json().build()),
                                  name="json")

    class Address(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        city: str

    class Person(OutputModel):
        __match__ = M("document", "array", "object", record=True)
        name: str
        address: Address | None = None

    SRC = '[{"name": "ann", "address": {"city": "Paris"}}]'
    bare = [r.model_dump() for r in
            Person.extract(SRC, language=tree_sitter_json)]
    bound_lang = Language.load(tree_sitter_json.language(), schema=schema)
    Person.validate_with(bound_lang)
    bound = [r.model_dump() for r in Person.extract(SRC, language=bound_lang)]
    assert bound == bare


@pytest.mark.xfail(strict=True, reason="F-A3: NodeKind tuple alternation "
                                       "dropped in field mode — Phase 4.3")
def test_fa3_nodekind_tuple_emits_all_kinds_in_field_mode():
    import tree_sitter_python
    from tsquery import Language, M, OutputModel, NodeKind, capture
    from typing import Annotated

    class Flag(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: str = capture("left")
        value: Annotated[str, NodeKind(("true", "false"))] = capture("right")

    py = Language.load(tree_sitter_python.language())
    rows = [r.model_dump() for r in Flag.extract("A = True\nB = False\n",
                                                 language=py)]
    assert sorted(r["value"] for r in rows) == ["False", "True"]


@pytest.mark.xfail(strict=True, reason="NEW list-branch: '...' path filter "
                                       "skipped for list[T] fields — 4.3")
def test_list_field_with_gap_path_filters_by_ancestry():
    """A model with a list[T] field and a '...' path over input where the
    anchor's ancestry does NOT match must yield ZERO rows — the scalar
    branch filters, the list branch must too (one matcher, one call site)."""
    import tree_sitter_python
    from tsquery import Language, M, OutputModel, capture

    class NeverCall(OutputModel):
        __match__ = M("object", ..., "call")   # top-level call is under module
        args: list[str] = capture("arguments")

    py = Language.load(tree_sitter_python.language())
    rows = [r.model_dump() for r in
            NeverCall.extract("f(1, 2)\ng(3)\n", language=py)]
    assert rows == []


@pytest.mark.xfail(strict=True, reason="T-1: _ir_derive choice-order "
                                       "required diverges from the CLI — "
                                       "port deleted in Phase 3")
def test_t1_choice_order_required_matches_cli():
    """The same grammar modulo choice order must derive the SAME schema, and
    the field must be non-required (one branch lacks it — the CLI emits
    required:false for both orders). Current: the 2nd-branch order reports
    required:true. Phase 3 makes this true by construction (the schema IS
    the CLI byproduct)."""
    import tsgrammar as tg
    from tscore.schema import NodeSchema, derive_from_ir

    def derive(first, second):
        g = tg.Grammar("t1")
        g.start("x")
        g.rule("x", tg.choice(first, second))
        g.rule("a", "a")
        g.rule("b", "b")
        return NodeSchema.from_list(derive_from_ir(g.build()), name="t1")

    s1 = derive(tg.field("f", tg.ref("b")), "a")   # field in 1st branch
    s2 = derive("a", tg.field("f", tg.ref("b")))   # field in 2nd branch

    def field_required(s):
        for nt in s.node_types:
            if nt.type == "x":
                f = nt.fields.get("f")
                return f.required if f else None
        return None

    assert field_required(s1) is False
    assert field_required(s2) is False
    assert s1.to_json() == s2.to_json()


# ---------------------------------------------------------------------------
# --generate mode: regenerate the oracle JSONs from current code
# ---------------------------------------------------------------------------

def _generate() -> int:
    from tsgrammar.schema_tool import build_community_bundle
    from tsquery import Language

    built = ORACLES / ".built"
    built.mkdir(parents=True, exist_ok=True)

    bash_mod = _import_example("bash-extract")
    bash = build_community_bundle(BASH_FIXTURE, built / "bash",
                                  name="bash", keep=False)
    (ORACLES / "bash-extract.json").write_text(json.dumps(
        collect_bash(bash_mod, Language.load_bundle(bash)), indent=2) + "\n")

    nix_mod = _import_example("devenv-extract")
    nix = build_community_bundle(NIX_FIXTURE, built / "nix",
                                 name="nix", keep=False)
    (ORACLES / "devenv-extract.json").write_text(json.dumps(
        collect_nix(nix_mod, Language.load_bundle(nix)), indent=2) + "\n")

    subset_mod = _import_example("devenv-subset")
    subset_bundle = build_subset_bundle(subset_mod, built / "subset")
    (ORACLES / "devenv-subset.json").write_text(json.dumps(
        collect_subset(subset_mod, Language.load_bundle(subset_bundle)),
        indent=2) + "\n")

    shutil.rmtree(built, ignore_errors=True)
    print("wrote tests/oracles/{bash-extract,devenv-extract,"
          "devenv-subset}.json")
    return 0


if __name__ == "__main__":
    if "--generate" in sys.argv:
        raise SystemExit(_generate())
    raise SystemExit(pytest.main([__file__, "-q"]))
