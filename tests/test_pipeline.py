"""Pipeline tests: grammar.json hashing, ABI-15 emission, and (toolchain
permitting) the full generate -> gcc -> load -> parse round-trip with the
content-addressed cache."""

from __future__ import annotations

import shutil

import pytest

import pydantree_sitter_grammar as tg

pytestmark = pytest.mark.toolchain


@pytest.fixture()
def cache_dir(tmp_path):
    return tmp_path / "cache"


def _simple_grammar() -> tg.Grammar:
    g = tg.Grammar("pipeline_t")
    g.rule("number", tg.pattern(r"\d+(\.\d+)?"))
    g.rule("source_file", tg.repeat(tg.ref("number")))
    g.start("source_file")
    g.extra(tg.pattern(r"\s"))  # grammar.json has no default whitespace extra
    return g


def test_build_warnings_surface(cache_dir):
    """B15: analyzer warnings are attached to the BuildResult (they used to
    be computed then discarded) and cite the author's source when the build
    goes through build_builder."""
    g = tg.Grammar("warn_t")
    g.precedence_ordering("low")   # declare the named precedence (CLI-required)
    g.rule("x", tg.choice(
        tg.prec("low", tg.ref("a")),
        tg.prec(1, tg.ref("b"))))
    g.rule("a", "a")
    g.rule("b", "b")
    g.rule("source_file", tg.ref("x"))
    g.start("source_file")

    result = tg.build_builder(g, cache_dir=cache_dir)
    assert result.warnings, "expected a precedence-mixing warning"
    assert any("precedence" in w.message for w in result.warnings)
    # the site-carrying run: warnings cite the author's file (this test file)
    assert all(w.site is None or w.site.file.endswith("test_pipeline.py")
               for w in result.warnings)

    # a warning-free grammar -> empty warnings
    clean = tg.build_builder(tg.Grammar("clean_t")
                             .rule("source_file", tg.pattern(r"\w+"))
                             .start("source_file"),
                             cache_dir=cache_dir)
    assert clean.warnings == []


def test_bundle_abi_matches_the_built_language(cache_dir, tmp_path, monkeypatch):
    """B16: the bundle's `abi` metadata must come from the same source as
    the cache key (_python_abi -> LANGUAGE_VERSION), not a separate env read
    that can claim ABI 15 for a 14 artifact. A stale TSGRAMMAR_ABI override
    must NOT leak into the bundle metadata."""
    import json
    import tree_sitter as _ts
    from pydantree_sitter_grammar.pipeline import write_bundle

    monkeypatch.setenv("TSGRAMMAR_ABI", "9")  # a stale override (B16)
    result = tg.build_builder(_simple_grammar(), cache_dir=cache_dir)
    bundle = write_bundle(result, tmp_path / "bundle")
    meta = json.loads((bundle / "tree-sitter.json").read_text())
    assert meta["abi"] == str(_ts.LANGUAGE_VERSION)
    assert meta["abi"] != "9"


def test_grammar_hash_is_content_addressed():
    a = _simple_grammar().build()
    b = _simple_grammar().build()
    assert tg.grammar_hash(a) == tg.grammar_hash(b)
    c = _simple_grammar()
    c.rule("extra", tg.pattern(r"\w+"))  # changes nothing reachable? it does
    assert tg.grammar_hash(c.build()) != tg.grammar_hash(a)


def test_cache_key_distinguishes_grammar_name(cache_dir):
    """B13: the cache key must fold grammar_name in — the .so filename
    embeds it, so two names for the same model must not share an entry."""
    from pydantree_sitter_grammar.pipeline import build

    m = _simple_grammar().build()
    r1 = build(m, cache_dir=cache_dir, grammar_name="alpha")
    r2 = build(m, cache_dir=cache_dir, grammar_name="beta")
    assert r1.so_path.exists() and r2.so_path.exists()
    assert r1.so_path != r2.so_path


def test_promote_race_is_graceful(cache_dir):
    """B14: a concurrent build winning the promote race leaves a populated
    entry; os.rename onto it raises OSError(ENOTEMPTY) on Linux (not
    FileExistsError) — the loser must discard its work dir, not crash."""
    g = _simple_grammar()
    first = tg.build_builder(g, cache_dir=cache_dir)
    assert first.so_path.exists()

    # force the promote path: the entry exists (a concurrent build won) but
    # its grammar.json is missing, so the cache-hit short-circuit can't fire
    first.grammar_json.unlink()
    result = tg.build_builder(g, cache_dir=cache_dir)
    assert result.so_path.exists()
    assert not (cache_dir / ".work").exists() or not any(
        (cache_dir / ".work").iterdir())


def test_emit_bundle_writes_abi15_config(tmp_path):
    model = _simple_grammar().build()
    json_path = model.emit_bundle(tmp_path)
    assert json_path.exists()
    cfg = tmp_path / "tree-sitter.json"
    assert cfg.exists()
    assert '"0.1.0"' in cfg.read_text()


def test_full_pipeline_generate_compile_load_parse(cache_dir):
    g = _simple_grammar()
    result = tg.build_builder(g, cache_dir=cache_dir)
    assert result.generate_proc is not None
    assert result.generate_proc.returncode == 0
    assert result.compile_proc is not None
    assert result.compile_proc.returncode == 0
    assert result.so_path.exists()
    lang, _lib = tg.load_language(result.so_path, "pipeline_t")
    assert lang.abi_version == 15

    tree = tg.parse(lang, "1 2 3.5")
    assert not tree.root_node.has_error
    assert tree.root_node.named_children[0].text.decode() == "1"

    # second build hits the cache
    result2 = tg.build_builder(g, cache_dir=cache_dir)
    assert result2.cached is True
    lang2, _ = tg.load_language(result2.so_path, "pipeline_t")
    tree2 = tg.parse(lang2, "1 2 3.5")
    assert not tree2.root_node.has_error


def test_analyzer_is_prerequisite_for_pipeline(cache_dir):
    """The unused-rule footgun: the CLI generates SUCCESSFULLY but silently
    prunes the orphan rule — the analyzer must catch it before the pipeline."""
    g = tg.Grammar("pruned")
    g.rule("used", tg.pattern(r"\d+"))
    g.rule("orphan", tg.pattern(r"\w+"))
    g.rule("source_file", tg.repeat(tg.ref("used")))
    g.start("source_file")
    issues = tg.errors(g)
    assert any("unused rule" in i.message for i in issues)

    # D10: the analyzer is PART of build() by default — the orphan aborts
    with pytest.raises(tg.GrammarCheckError):
        tg.build_builder(g, cache_dir=cache_dir)
    # the silent trap, demonstrated with the explicit opt-out: generate
    # succeeds, the parser lacks the rule
    result = tg.build_builder(g, cache_dir=cache_dir, check=False)
    node_types = result.node_types_json.read_text()
    assert '"orphan"' not in node_types


def test_generate_conflict_raises_named_error(cache_dir):
    g = tg.Grammar("conflict_t")
    g.rule("number", tg.pattern(r"\d+"))
    g.rule("expr", tg.choice(
        tg.seq(tg.ref("expr"), "+", tg.ref("expr")),
        tg.ref("number")))
    g.rule("source_file", tg.repeat(tg.ref("expr")))
    g.start("source_file")
    import pydantree_sitter_grammar as tgm
    from pydantree_sitter_grammar.conflicts import remap_from_proc
    json_path = g.emit_bundle(cache_dir / "conflict_t")
    proc = tgm.run_generate(json_path)   # always --json (D10)
    assert proc.returncode == 1
    conflict, err = remap_from_proc(g, proc)
    assert conflict.involved_rules == ["expr"]
    assert "Ambiguous shape" in str(err)
    assert g.sites["expr"].file.endswith("test_pipeline.py")


# ---------------------------------------------------------------------------
# 014 refactor Phase 3 (D3/D12): the schema IS the CLI byproduct, and the
# T-1 repro (choice-order `required` divergence in the deleted node_types
# hand-port) becomes trivially true by construction
# ---------------------------------------------------------------------------

def test_bundle_schema_is_the_generate_byproduct_byte_for_byte(cache_dir):
    """The bundle's node-schema.json is byte-identical to the generate run's
    node-types.json — correct by construction (D3: the schema's only source
    is the CLI byproduct; the port is deleted). This test documents the
    contract; it cannot drift."""
    model = _simple_grammar().build()
    res = tg.build(model, cache_dir=cache_dir)
    assert res.node_schema_json.read_bytes() == res.node_types_json.read_bytes()

    # a warm-cache second build re-reads the same bytes (no re-derivation)
    res2 = tg.build(model, cache_dir=cache_dir)
    assert res2.cached is True
    assert res2.node_schema_json.read_bytes() == res.node_schema_json.read_bytes()


def test_choice_order_required_matches_cli_by_construction(cache_dir):
    """The T-1 repro (AGENT_REPORTS Report 3): the same grammar modulo choice
    order used to derive different field-required in the port (2nd-branch
    order -> required:true, diverging from the CLI's false). With the port
    deleted, the schema IS the CLI byproduct — both orders report whatever
    the CLI reports, byte-identically by construction."""
    def build_order(first, second):
        g = tg.Grammar("t1")
        g.start("x")
        g.rule("x", tg.choice(first, second))
        g.rule("a", "a")
        g.rule("b", "b")
        return tg.build(g.build(), cache_dir=cache_dir)

    r1 = build_order(tg.field("f", tg.ref("b")), tg.ref("a"))  # 1st branch
    r2 = build_order(tg.ref("a"), tg.field("f", tg.ref("b")))  # 2nd branch
    assert r1.node_schema_json.read_bytes() == r2.node_schema_json.read_bytes()

    from pydantree_sitter.schema import NodeSchema

    def field_required(schema):
        for nt in schema.node_types:
            if nt.type == "x":
                f = nt.fields.get("f")
                return f.required if f else None
        return None

    s1 = NodeSchema.from_node_types_json(r1.node_schema_json, name="t1")
    s2 = NodeSchema.from_node_types_json(r2.node_schema_json, name="t1")
    assert field_required(s1) == field_required(s2)


def test_bodyless_external_emits_scanner_token_not_literal_text(cache_dir, tmp_path):
    """B12 (REVIEW 018): a bodyless External class must produce a body the
    CLI resolves to the DECLARED external (pymini's tok() convention), not a
    literal-text token for the string 'FRAG'. End-to-end: generate succeeds
    with ONE kind, and a scanner emitting the external makes even non-'FRAG'
    text parse — a literal-text token could only parse the text 'FRAG'."""
    import sys
    import types

    src = (
        "from pydantree_sitter_grammar import Rule, External, assemble\n"
        "class Frag(External):\n"
        "    pass\n"
        "def build():\n"
        "    return assemble('ext2', start=Frag, rules=[Frag])\n"
    )
    f = tmp_path / "ext_author.py"
    f.write_text(src)
    mod = types.ModuleType("ext_author")
    mod.__file__ = str(f)
    sys.modules["ext_author"] = mod
    try:
        exec(compile(src, str(f), "exec"), mod.__dict__)
        g = mod.build()
        # the scanner that emits the single external (symbol 0)
        scanner = tmp_path / "scanner.c"
        scanner.write_text(r'''
#include "tree_sitter/parser.h"
void *tree_sitter_ext2_external_scanner_create() { return NULL; }
void tree_sitter_ext2_external_scanner_destroy(void *p) {}
unsigned tree_sitter_ext2_external_scanner_serialize(void *p, char *b) { return 0; }
void tree_sitter_ext2_external_scanner_deserialize(void *p, const char *b, unsigned n) {}
bool tree_sitter_ext2_external_scanner_scan(void *p, TSLexer *lexer, const bool *valid_symbols) {
  lexer->advance(lexer, false);
  lexer->mark_end(lexer);
  lexer->result_symbol = 0;
  return true;
}
''')
        result = tg.build_builder(g, cache_dir=cache_dir, scanner=scanner)
        lang, _ = tg.load_language(result.so_path, "ext2")
        # one kind in node-types — no extra literal 'FRAG' token
        node_types = result.node_types_json.read_text()
        assert node_types.count('"FRAG"') == 1, node_types
        # the external fires for ANY token: 'h' parses via the scanner — a
        # literal-text token could only parse the text 'FRAG'
        tree = tg.parse(lang, "h")
        assert not tree.root_node.has_error
        assert tree.root_node.child_count == 1
    finally:
        sys.modules.pop("ext_author", None)
