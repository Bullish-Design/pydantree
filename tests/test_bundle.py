"""Phase-5 bundle tests: the artifact seam in production.

Covers: BuildResult.package() emits a shippable bundle (grammar.so +
node-schema.json + tree-sitter.json metadata + a 7-line loader that delegates
to tscore's shared loading contract); tsquery.Language.load_bundle consumes
it in ONE call; the bundle is consumed in a SEPARATE process where tsgrammar
is NOT importable (sitecustomize strips the editable src/ install) with the
Phase-4 ground truth passing and the checks active; the community-schema tool
(grammar dir -> CLI generate -> node-types.json -> derive_from_node_types ->
node-schema.json) agrees with derive_from_ir and feeds a B-free community
consumer over the tree_sitter_json wheel; A's surface is byte-identical
in-process vs B-free.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

import tsgrammar as tg
from tsquery import (
    Language, M, OutputModel, capture, capture_kind, source_meta,
)

BRIDGE_DIR = Path(__file__).resolve().parents[1] / ".scratch" / "006-tsquery-bridge"
P5_DIR = Path(__file__).resolve().parents[1] / ".scratch" / "007-tsquery-distribution"
sys.path.insert(0, str(BRIDGE_DIR))
sys.path.insert(0, str(P5_DIR))

TOOLCHAIN_AVAILABLE = shutil.which("tree-sitter") is not None and \
    shutil.which("gcc") is not None

pytestmark = pytest.mark.skipif(
    not TOOLCHAIN_AVAILABLE, reason="tree-sitter CLI / gcc not on PATH")

from bfree import run_bfree  # noqa: E402
from cfg_grammar import (  # noqa: E402
    CORPUS,
    LISTEN_GROUND_TRUTH,
    SECTION_GROUND_TRUTH,
    build as build_cfg,
)
from json_grammar import build as build_json  # noqa: E402
from tsgrammar.language import load_language  # noqa: E402
from tsquery.schema import check_model_schema  # noqa: E402
from tscore.schema import NodeSchema, derive_from_ir  # noqa: E402


class ServerSection(OutputModel):
    __match__ = M("source_file", "section", record=True)
    host: str
    port: int
    debug: bool = False
    title: str | None = None
    line: int = source_meta()


class Listen(OutputModel):
    __match__ = M("source_file", "directive")
    name: str = capture("name")
    port: int = capture("arg")
    line: int = source_meta()


def _cfg_bundle(tmp_path) -> tuple[Path, tg.BuildResult]:
    g = build_cfg()
    result = tg.build_builder(g)
    bundle = result.package(tmp_path / "bundle")
    return bundle, result


# ---------------------------------------------------------------------------
# the bundle + the in-process round trip
# ---------------------------------------------------------------------------

def test_package_bundle_layout_and_loader():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        g = build_cfg()
        result = tg.build_builder(g)
        bundle = result.package(Path(td) / "bundle")
        files = {p.name: p.stat().st_size for p in bundle.iterdir()}
        assert set(files) == {"grammar.so", "node-schema.json",
                              "tree-sitter.json", "loader.py"}
        meta = json.loads((bundle / "tree-sitter.json").read_text())
        assert meta["name"] == "cfg"
        assert meta["artifact"] == "grammar.so"
        assert meta["schema"] == "node-schema.json"
        loader_lines = (bundle / "loader.py").read_text().splitlines()
        assert len(loader_lines) <= 8, loader_lines
        assert "tscore.loader" in (bundle / "loader.py").read_text()
        assert "tsgrammar" not in (bundle / "loader.py").read_text()


def test_load_bundle_one_liner_checks_and_truth(tmp_path):
    bundle, _ = _cfg_bundle(tmp_path)
    lang = Language.load_bundle(bundle)          # the one-liner
    ServerSection.validate_with(lang)            # checks active
    Listen.validate_with(lang)
    secs = [r.model_dump() for r in ServerSection.extract(CORPUS, language=lang)]
    listens = [r.model_dump() for r in Listen.extract(CORPUS, language=lang)]
    assert secs == SECTION_GROUND_TRUTH
    assert listens == LISTEN_GROUND_TRUTH
    # the schema rides the bundle (the bridge artifact)
    assert lang.schema is not None
    check_model_schema(ServerSection, lang.schema)


# ---------------------------------------------------------------------------
# the B-free subprocess (Run 2)
# ---------------------------------------------------------------------------

def test_bundle_consumed_in_bfree_subprocess(tmp_path):
    bundle, _ = _cfg_bundle(tmp_path)
    rc, out = run_bfree(P5_DIR / "consumer.py", str(bundle), workdir=tmp_path)
    assert rc == 0, out
    data = json.loads(out)
    assert data["ok"] is True
    assert data["sections"] == SECTION_GROUND_TRUTH
    assert data["directives"] == LISTEN_GROUND_TRUTH
    assert data["schema_bound"] is True
    assert "tsgrammar" not in out  # the consumer asserts B is unimportable


def test_bfree_consumer_surface_byte_identical(tmp_path):
    """A's extract output is byte-identical with and without B in the process
    (the same model code, same language, two processes)."""
    bundle, _ = _cfg_bundle(tmp_path)
    lang = Language.load_bundle(bundle)
    inproc = [r.model_dump() for r in ServerSection.extract(CORPUS, language=lang)]
    rc, out = run_bfree(P5_DIR / "consumer.py", str(bundle), workdir=tmp_path)
    assert rc == 0
    bfree = json.loads(out)["sections"]
    assert inproc == bfree == SECTION_GROUND_TRUTH


# ---------------------------------------------------------------------------
# the community path (schema tool -> wheel -> B-free consumer)
# ---------------------------------------------------------------------------

def test_community_schema_tool_agrees_and_feeds_bfree_consumer(tmp_path):
    from tsgrammar.schema_tool import derive_schema_for_dir
    json_model = build_json().build()
    # materialize the json grammar source dir (grammar.json + tree-sitter.json)
    src_dir = tmp_path / "json_grammar"
    json_model.emit_bundle(src_dir)
    derived = derive_schema_for_dir(src_dir, name="json",
                                    workdir=tmp_path / "cw",
                                    out=tmp_path / "cw" / "node-schema.json",
                                    keep=True)
    # agreement with the exact path on the shared subset (the Phase-4 check)
    from_ir = NodeSchema.from_list(derive_from_ir(json_model), name="json")
    assert derived.to_json() == from_ir.to_json()

    # the B-free community consumer: wheel + derived schema, no B
    schema_path = tmp_path / "cw" / "node-schema.json"
    rc, out = run_bfree(P5_DIR / "consumer_community.py", str(schema_path),
                        workdir=tmp_path)
    assert rc == 0, out
    data = json.loads(out)
    assert data["ok"] is True
    assert data["rows"][0]["name"] == "alice"
    assert data["rows"][2] == {"name": "carol", "age": 25, "tags": [],
                               "nickname": None, "active": False, "line": 15}


def test_community_schema_tool_cli(tmp_path):
    """The one-command tool: `python -m tsgrammar.schema_tool <dir>`."""
    import os
    import subprocess
    json_model = build_json().build()
    src_dir = tmp_path / "cli_grammar"
    json_model.emit_bundle(src_dir)
    env = dict(os.environ)
    proc = subprocess.run(
        [sys.executable, "-m", "tsgrammar.schema_tool", str(src_dir),
         "-o", str(tmp_path / "out.json"), "-n", "json"],
        capture_output=True, text=True, env=env, check=False)
    assert proc.returncode == 0, proc.stderr
    schema = NodeSchema.from_node_types_json(tmp_path / "out.json", name="json")
    assert "object" in schema.kinds() and "pair" in schema.kinds()


# ---------------------------------------------------------------------------
# Phase 6 — Run 2: the community seam over a REAL grammar (tree-sitter-rust)
# ---------------------------------------------------------------------------

RUST_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "rust"
P8_DIR = Path(__file__).resolve().parents[1] / ".scratch" / "008-consumer-seam"


def test_schema_tool_over_real_rust_source_byte_for_byte(tmp_path):
    """The community tool over the REAL tree-sitter-rust source (182 rules,
    11 externals): derive_schema_for_dir accepts the community layout, runs
    the CLI, and the derived schema is byte-for-byte the CLI's own
    node-types.json — no normalization, no shape differences."""
    from tsgrammar.schema_tool import derive_schema_for_dir
    out = tmp_path / "rust-schema.json"
    derived = derive_schema_for_dir(RUST_FIXTURE, name="rust",
                                    workdir=tmp_path / "cw",
                                    out=out, keep=True)
    assert derived.name == "rust"
    cli = (RUST_FIXTURE / "node-types.json").read_text()
    assert out.read_text() == cli


def test_community_bundle_build_and_bfree_extraction(tmp_path):
    """The full Run-2 path over a grammar we don't own: community source ->
    build_community_bundle (generate + gcc + schema + metadata + loader) ->
    B-free consumer (tsgrammar unimportable) -> hand-authored rust ground
    truth, checks active."""
    from tsgrammar.schema_tool import build_community_bundle
    bundle = build_community_bundle(RUST_FIXTURE, tmp_path / "bundle",
                                    name="rust", keep=True)
    assert set(p.name for p in bundle.iterdir()) == {
        "grammar.so", "node-schema.json", "tree-sitter.json", "loader.py"}
    rc, out = run_bfree(P8_DIR / "consumer_rust.py", str(bundle),
                        workdir=tmp_path / "bfree")
    assert rc == 0, out
    data = json.loads(out)
    assert data["ok"] is True
    assert data["schema_bound"] is True
    assert [r["name"] for r in data["fns"]] == \
        ["add", "main", "greet", "no_return"]
    assert data["tuple_structs"][0] == {
        "name": "Point", "types": ["f64", "f64"], "line": 18}
    assert "tsgrammar" not in out


def test_community_job1_catches_bad_path_over_real_rust(tmp_path):
    """The bridge check (Job 1) over a real grammar: a model whose M() chain
    names a kind the grammar cannot produce (tuple_type is not a node kind in
    rust — struct_item -> ordered_field_declaration_list directly) is
    rejected at validate_with, before any text is parsed."""
    from tsgrammar.schema_tool import build_community_bundle
    from tsquery import SchemaCheckError
    bundle = build_community_bundle(RUST_FIXTURE, tmp_path / "bundle",
                                    name="rust", keep=True)
    lang = Language.load_bundle(bundle)

    class BadChain(OutputModel):
        __match__ = M("source_file", "struct_item", "tuple_type",
                      "ordered_field_declaration_list")
        types: list[str] = capture("type")

    with pytest.raises(SchemaCheckError) as exc:
        BadChain.validate_with(lang)
    assert "tuple_type" in str(exc.value)
    assert "struct_item" in str(exc.value)


def test_optional_field_capture_is_query_optional(tmp_path):
    """Phase 6.5: a field-mode capture with an Optional type emits `?` in the
    derived query — matches WITHOUT the field still materialize (None), while
    a required capture (no Optional, no real default) stays required. This is
    the fix for the Phase-6 finding that `str | None = capture(...)` silently
    excluded every node lacking the field (real rust `fn no_return() {}`)."""
    from tsgrammar.schema_tool import build_community_bundle
    bundle = build_community_bundle(RUST_FIXTURE, tmp_path / "bundle",
                                    name="rust", keep=True)
    lang = Language.load_bundle(bundle)

    class RustFnReturn(OutputModel):
        __match__ = M("source_file", "function_item")
        name: str = capture("name")
        return_type: str | None = capture("return_type")
        line: int = source_meta()

    # the derived query makes the optional capture `?`-quantified
    src = RustFnReturn.compiled_source(schema=lang.schema, language=lang)
    assert "return_type:(_)? @return_type" in src, src
    rows = [r.model_dump() for r in RustFnReturn.extract(
        "fn add(a: u32) -> u32 { a }\nfn main() {}\n", language=lang)]
    assert rows == [{"name": "add", "return_type": "u32", "line": 1},
                    {"name": "main", "return_type": None, "line": 2}]

    class Required(OutputModel):
        __match__ = M("source_file", "function_item")
        name: str = capture("name")

    # a required capture (no Optional, no real default) is NOT quantified
    src2 = Required.compiled_source(schema=lang.schema, language=lang)
    assert "name:(_)?" not in src2
    assert "name:(_) @name" in src2, src2


def test_markdown_community_bundle_and_bfree_extraction(tmp_path):
    """The Phase-6.5 markdown rehearsal over the REAL tree-sitter-markdown
    grammars: build_community_bundle for the block + inline grammars, and the
    B-free consumer extracts BLOCK elements (headings via the heading_content
    FIELD, fenced code via the capture_kind() child-by-kind surface) and
    INLINE elements (code spans / emphasis / strong / links via a nested
    parse of the injected-style `inline` nodes) against hand truth."""
    from tsgrammar.schema_tool import build_community_bundle
    md = Path(__file__).resolve().parent / "fixtures" / "markdown"
    mdi = Path(__file__).resolve().parent / "fixtures" / "markdown-inline"
    block = build_community_bundle(md, tmp_path / "b-block", name="markdown")
    inline = build_community_bundle(mdi, tmp_path / "b-inline",
                                    name="markdown_inline")
    rc, out = run_bfree(P8_DIR / "consumer_markdown.py", str(block),
                        str(inline), workdir=tmp_path / "bfree")
    assert rc == 0, out
    data = json.loads(out)
    assert data["ok"] is True
    assert data["headings"] == [{"text": "Title", "line": 1},
                                {"text": "Section", "line": 5}]
    assert data["fenced"][0]["info"] == "python"
    assert data["code_spans"] == ["`code`"]
    assert data["links"] == [{"dest": "https://example.com", "line": 3}]
    assert "tsgrammar" not in out


def test_capture_kind_job1_rejects_non_child(tmp_path):
    """capture_kind()'s Job-1 check: a kind that is NOT a direct child of the
    anchor is rejected before parsing (real markdown: `language` sits under
    info_string, not on fenced_code_block; `link_destination` sits under
    inline_link, not on inline)."""
    from tsgrammar.schema_tool import build_community_bundle
    from tsquery import SchemaCheckError
    md = Path(__file__).resolve().parent / "fixtures" / "markdown"
    block = build_community_bundle(md, tmp_path / "b-block", name="markdown")
    lang = Language.load_bundle(block)

    class BadKind(OutputModel):
        __match__ = M("document", ..., "fenced_code_block")
        language: str | None = capture_kind("language")

    with pytest.raises(SchemaCheckError) as exc:
        BadKind.validate_with(lang)
    assert "language" in str(exc.value)
    assert "fenced_code_block" in str(exc.value)
