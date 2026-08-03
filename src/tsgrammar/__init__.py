"""
tsgrammar — author tree-sitter grammars in Pydantic (Product B core).

The pipeline: Grammar -> IR (grammar.json) -> tree-sitter generate -> gcc ->
.so -> load -> parse. Static analysis and conflict remapping happen in Python
with the author's DSL source sites attached.

Public surface:

    from tsgrammar import (
        Grammar,                    # the builder registry
        rule, seq, choice, repeat, repeat1, opt, field, token, tok,
        immediate_token, ref, pattern, alias, blank,
        prec, prec_left, prec_right, prec_dynamic,
        GrammarModel,               # the IR (grammar.json mirror)
        run_checks, errors, warnings, assert_clean, CheckIssue, GrammarCheckError,
        GrammarConflictError, Conflict, parse_conflict_json, remap_from_proc,
        build, build_builder, detect_toolchain, grammar_hash,
        load_language, parse,
    )
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
from .expressions import expression, semantic_smoke, DEFAULT_PRECEDENCE_CORPUS
from .grammar import (
    AliasNode,
    BlankNode,
    ChoiceNode,
    FieldNode,
    ImmediateTokenNode,
    PatternNode,
    PrecDynamicNode,
    PrecLeftNode,
    PrecNode,
    PrecRightNode,
    Repeat1Node,
    RepeatNode,
    ReservedNode,
    Rule,
    RuleNode,
    SeqNode,
    StrNode,
    SymbolNode,
    TokenNode,
)
from .grammar import (
    Grammar as GrammarModel,
)
from .language import load_language, parse
from .pipeline import (
    BuildResult,
    CompileError,
    GenerateError,
    PipelineError,
    build,
    build_builder,
    build_loop,
    compile_parser,
    debug_states,
    default_cache_dir,
    detect_toolchain,
    generate,
    grammar_hash,
    run_generate,
)

__version__ = "0.1.0"

__all__ = [
    # builder
    "Grammar", "rule", "seq", "choice", "repeat", "repeat1", "opt", "field",
    "token", "tok", "immediate_token", "ref", "pattern", "alias", "blank",
    "prec", "prec_left", "prec_right", "prec_dynamic", "grammar",
    "RuleSite", "B", "Ladder",
    # IR
    "GrammarModel", "Rule", "RuleNode",
    "SymbolNode", "StrNode", "PatternNode", "BlankNode", "SeqNode",
    "ChoiceNode", "RepeatNode", "Repeat1Node", "FieldNode", "AliasNode",
    "TokenNode", "ImmediateTokenNode", "PrecNode", "PrecLeftNode",
    "PrecRightNode", "PrecDynamicNode", "ReservedNode",
    # analyzer
    "run_checks", "errors", "warnings", "assert_clean", "CheckIssue",
    "GrammarCheckError",
    # conflicts
    "GrammarConflictError", "Conflict", "parse_conflict_json", "remap_from_proc",
    # pipeline
    "build", "build_builder", "build_loop", "generate", "run_generate",
    "compile_parser", "debug_states", "detect_toolchain", "grammar_hash",
    "default_cache_dir", "BuildResult", "PipelineError", "GenerateError",
    "CompileError",
    # expression helper
    "expression", "semantic_smoke", "DEFAULT_PRECEDENCE_CORPUS",
    # language
    "load_language", "parse",
]
