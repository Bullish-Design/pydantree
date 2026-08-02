"""Pipeline tests: grammar.json hashing, ABI-15 emission, and (toolchain
permitting) the full generate -> gcc -> load -> parse round-trip with the
content-addressed cache."""

from __future__ import annotations

import shutil

import pytest

import tsgrammar as tg

TOOLCHAIN_AVAILABLE = shutil.which("tree-sitter") is not None and \
    shutil.which("gcc") is not None

pytestmark = pytest.mark.skipif(
    not TOOLCHAIN_AVAILABLE, reason="tree-sitter CLI / gcc not on PATH")


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


def test_grammar_hash_is_content_addressed():
    a = _simple_grammar().build()
    b = _simple_grammar().build()
    assert tg.grammar_hash(a) == tg.grammar_hash(b)
    c = _simple_grammar()
    c.rule("extra", tg.pattern(r"\w+"))  # changes nothing reachable? it does
    assert tg.grammar_hash(c.build()) != tg.grammar_hash(a)


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

    # the silent trap, demonstrated: generate succeeds, parser lacks the rule
    result = tg.build_builder(g, cache_dir=cache_dir)
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
    import tsgrammar as tgm
    from tsgrammar.conflicts import remap_from_proc
    json_path = g.emit_bundle(cache_dir / "conflict_t")
    proc = tgm.run_generate(json_path, json_report=True)
    assert proc.returncode == 1
    conflict, err = remap_from_proc(g, proc)
    assert conflict.involved_rules == ["expr"]
    assert "Ambiguous shape" in str(err)
    assert g.sites["expr"].file.endswith("test_pipeline.py")
