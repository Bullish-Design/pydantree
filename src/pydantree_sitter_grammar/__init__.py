"""
pydantree_sitter_grammar — author tree-sitter grammars in Pydantic (Product B).

The pipeline: Grammar -> IR (grammar.json) -> tree-sitter generate -> gcc ->
.so -> load -> parse. Static analysis and conflict remapping happen in Python
with the author's DSL source sites attached.

Public surface:

    from pydantree_sitter_grammar import (
        Grammar,                    # the builder registry
        seq, choice, repeat, repeat1, opt, field, token, tok,
        immediate_token, ref, pattern, alias, blank,
        prec, prec_left, prec_right, prec_dynamic,
        GrammarModel,               # the IR (grammar.json mirror)
        run_checks, errors, warnings, assert_clean, CheckIssue, GrammarCheckError,
        GrammarConflictError, Conflict, parse_conflict_json, remap_from_proc,
        build, build_builder, detect_toolchain, grammar_hash,
        load_language, parse,
    )

The RULE-CLASS surface ("the model IS the rule"): author each grammar rule
as a class — the base class is the rule's kind (Pattern/Token/External +
Extra/Supertype/Hidden/Inline/Word mixins), annotated attributes are ordered
children, `__body__` is the combinator escape hatch, and `assemble()`
compiles the classes into the same builder `Grammar`:

    from pydantree_sitter_grammar import (External, Extra, Pattern, R, Rule,
                                          Supertype, Token, assemble)

    class Pair(Rule):
        key: NamePath
        eq: Literal["="] = "="
        value: Value

    def build() -> Grammar:
        return assemble("devenv", start=SourceFile)

`Rule` is the AUTHORING base class only. The IR node union that used to share
the name lives at `pydantree_sitter_grammar.ir.Rule` (the node types —
SymbolNode, StrNode, SeqNode, ... — are exported as before). Same for the two
`Grammar`s: `Grammar` is the builder; the IR container is
`ir.GrammarModel`. See `pydantree_sitter_grammar.rules`.
"""

# ruff: noqa: RUF022  (grouped-by-layer __all__, not flat-sorted)

from __future__ import annotations

from .builder import (
    B,
    Grammar,
    Ladder,
    RuleSite,
    alias,
    blank,
    choice,
    field,
    grammar,
    immediate_token,
    opt,
    pattern,
    prec,
    prec_dynamic,
    prec_left,
    prec_right,
    ref,
    repeat,
    repeat1,
    seq,
    tok,
    token,
)
from .checks import (
    CheckIssue,
    GrammarCheckError,
    assert_clean,
    errors,
    run_checks,
    warnings,
)
from .conflicts import (
    Conflict,
    GrammarConflictError,
    parse_conflict_json,
    remap_from_proc,
)
from .corpus import (
    Corpus,
    CorpusCase,
    CorpusResult,
    corpus_case,
    render,
    render_compact,
)
from .expressions import DEFAULT_PRECEDENCE_CORPUS, expression, semantic_smoke
from .ir import (
    AliasNode,
    BlankNode,
    ChoiceNode,
    FieldNode,
    GrammarModel,
    ImmediateTokenNode,
    PatternNode,
    PrecDynamicNode,
    PrecLeftNode,
    PrecNode,
    PrecRightNode,
    Repeat1Node,
    RepeatNode,
    ReservedNode,
    RuleNode,
    SeqNode,
    StrNode,
    SymbolNode,
    TokenNode,
)
from .language import load_language, parse
from .pipeline import (
    BuildResult,
    CompileError,
    ExternalScannerRequiredError,
    GenerateError,
    PipelineError,
    Toolchain,
    build,
    build_builder,
    build_from_source_dir,
    build_loop,
    compile_parser,
    debug_states,
    default_cache_dir,
    detect_toolchain,
    grammar_hash,
    run_generate,
    write_bundle,
)
from .rules import (
    External,
    Extra,
    Hidden,
    Inline,
    Pattern,
    R,
    Rule,
    Supertype,
    Token,
    Word,
    assemble,
    module_rules,
)
from .scanners import (
    bash_heredoc_scanner_path,
    heredoc_scanner_path,
    indent_scanner_path,
    matched_delimiter_scanner_path,
    py_indent_scanner_path,
    scanner_for,
)
from .schema_tool import build_community_bundle, derive_schema_for_dir

__version__ = "0.4.0"

__all__ = [
    # builder
    "Grammar", "seq", "choice", "repeat", "repeat1", "opt", "field",
    "token", "tok", "immediate_token", "ref", "pattern", "alias", "blank",
    "prec", "prec_left", "prec_right", "prec_dynamic", "grammar",
    "RuleSite", "B", "Ladder",
    # IR (the node union `ir.Rule` is NOT exported under that name — `Rule`
    # below is the rule-class base; the union stays reachable as
    # `pydantree_sitter_grammar.ir.Rule`)
    "GrammarModel", "RuleNode",
    "SymbolNode", "StrNode", "PatternNode", "BlankNode", "SeqNode",
    "ChoiceNode", "RepeatNode", "Repeat1Node", "FieldNode", "AliasNode",
    "TokenNode", "ImmediateTokenNode", "PrecNode", "PrecLeftNode",
    "PrecRightNode", "PrecDynamicNode", "ReservedNode",
    # rule-class surface (the model IS the rule)
    "Rule", "Pattern", "Token", "External",
    "Extra", "Supertype", "Hidden", "Inline", "Word",
    "R", "assemble", "module_rules",
    # analyzer
    "run_checks", "errors", "warnings", "assert_clean", "CheckIssue",
    "GrammarCheckError",
    # conflicts
    "GrammarConflictError", "Conflict", "parse_conflict_json", "remap_from_proc",
    # corpus (Phase 5)
    "Corpus", "CorpusCase", "CorpusResult", "corpus_case", "render",
    "render_compact",
    # pipeline
    "build", "build_builder", "build_loop", "run_generate",
    "compile_parser", "debug_states", "detect_toolchain", "grammar_hash",
    "default_cache_dir", "BuildResult", "PipelineError", "GenerateError",
    "CompileError", "ExternalScannerRequiredError",
    "Toolchain", "write_bundle", "build_from_source_dir",
    # scanner library seed
    "indent_scanner_path", "heredoc_scanner_path",
    "matched_delimiter_scanner_path", "scanner_for",
    # Phase-7 per-language copies
    "py_indent_scanner_path", "bash_heredoc_scanner_path",
    # expression helper
    "expression", "semantic_smoke", "DEFAULT_PRECEDENCE_CORPUS",
    # language
    "load_language", "parse",
    "derive_schema_for_dir", "build_community_bundle",
]
