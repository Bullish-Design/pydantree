"""pydantree_sitter.pattern — structural search and rewrite (022 §3).

    lang = Language.from_module(tree_sitter_python)
    pat = Pattern("def $NAME($$$ARGS): $$$BODY", language=lang)

    for m in pat.find_all(source):
        m.span                  # Span
        m.node                  # tree_sitter.Node, in pydantree's own tree
        m.captures["NAME"]      # Span
        m.captures["ARGS"]      # tuple[Span, ...] for a $$$ metavariable
        m.extract(FunctionDef)  # list[OutputModel], scoped to this match

The division of labour (§17.1):

    ast-grep finds. pydantree resolves and types.

The module is text in, data out. It reads no file and writes none. A rewrite
returns `Edit` records and the new text; the caller decides what to do with
them.

`match.py` is a different thing entirely — it holds the `M()` ancestor-path
matcher over tree-sitter queries. The two modules never import each other. In
this module a `metavariable` is a `$NAME`; a `capture` in the rest of the
repository is an `OutputModel` field binding. `PatternMatch.captures` holds
metavariables, and that is the one place the two vocabularies touch.

Every offset here is a BYTE offset over UTF-8. ast-grep's own offsets are
CHARACTER offsets and are converted at the boundary — see
`agreement.char_to_byte_table`.
"""

from __future__ import annotations

import re
import warnings
from itertools import pairwise
from typing import Any

import tree_sitter
from pydantic import BaseModel, ConfigDict

from .agreement import (
    GrammarAgreement,
    agreement_for,
    char_to_byte_table,
)
from .agreement import dist_version as _dist_version
from .errors import (
    PatternBuildError,
    PatternError,
    PatternResolutionError,
    PatternRewriteError,
    PydantreeSitterError,
    UnsupportedLanguageError,
)
from .materialize import Span
from .rules import Rule, metavariables_of

__all__ = ["Edit", "Pattern", "PatternMatch", "ReplaceResult",
           "register_bundle_language", "registered_languages"]


# ---------------------------------------------------------------------------
# dynamic languages — a pydantree-built grammar, used BY ast-grep
# ---------------------------------------------------------------------------
#
# CONCEPT §7 says a grammar built by `pydantree-sitter-grammar` "has no
# ast-grep support". That is wrong. `ast_grep_py.register_dynamic_language`
# takes any tree-sitter shared library, and `write_bundle` produces exactly
# one.
#
# The consequence is larger than a feature. §4's whole premise is TWO
# grammars — ast-grep's vendored copy and pydantree's wheel — and the risk
# that they disagree. Register the bundle and there is only ONE artifact,
# loaded by both engines. Agreement stops being a measurement and becomes a
# construction: the node sets are identical because they come from the same
# parser.
#
# Registration is PROCESS-GLOBAL, which is ast-grep's design and not
# something this module can scope. `_REGISTERED` records what was registered
# under each name, so a second call with the same artifact is a no-op and a
# second call with a DIFFERENT artifact is an error rather than a silent
# rebind of every Pattern already built on that name.
_REGISTERED: dict[str, tuple[str, str]] = {}


def registered_languages() -> dict[str, tuple[str, str]]:
    """The dynamic languages this process registered: name -> (path, symbol)."""
    return dict(_REGISTERED)


def register_bundle_language(name: str, library_path, symbol: str, *,
                             extensions=None,
                             meta_var_char: str | None = None,
                             expando_char: str | None = None) -> str:
    """Make a tree-sitter shared library available to ast-grep as `name`.

    `Language.register_astgrep()` is the ergonomic entry point; this is the
    primitive, for a `.so` that did not come from a bundle.

    `extensions` is REQUIRED by the engine even though `ast_grep_py`'s own
    `CustomLang` type marks it optional — omitting it fails with
    ``missing field `extensions```. It defaults to `[name]` here, because
    this module never looks at a file name anyway.

    `meta_var_char` is the sigil a pattern uses for a metavariable, `$` by
    default. It must LEX AS AN IDENTIFIER in the target grammar, or pattern
    strings will not parse and every search silently returns nothing. That is
    why a `$H` pattern finds nothing in JSON: `$` is not a JSON token. A
    grammar whose content is free-form text (markdown) is fine with the
    default.

    Idempotent for an identical re-registration; raises on a conflicting one.
    """
    library_path = str(library_path)
    previous = _REGISTERED.get(name)
    if previous == (library_path, symbol):
        return name
    if previous is not None:
        raise PatternBuildError(
            f"ast-grep language {name!r} is already registered in this "
            f"process from {previous[0]!r} (symbol {previous[1]!r}); "
            f"re-registering it from {library_path!r} would silently rebind "
            f"every Pattern already built on it. Registration is "
            f"process-global — pick another name.")

    engine = _load_engine()
    config = {"library_path": library_path, "language_symbol": symbol,
              "extensions": list(extensions) if extensions else [name]}
    if meta_var_char is not None:
        config["meta_var_char"] = meta_var_char
    if expando_char is not None:
        config["expando_char"] = expando_char
    with _engine_errors(f"ast-grep refused the dynamic language {name!r}"):
        engine.register_dynamic_language({name: config})
    _REGISTERED[name] = (library_path, symbol)
    return name

# `$NAME` and `$$$NAME`, with the arity kept this time — the rewrite half
# needs to know which metavariables expand to a sequence.
_METAVAR = re.compile(r"\$(\$\$)?([A-Z_][A-Z0-9_]*)")


def _metavar_arity(pattern: str) -> dict[str, bool]:
    """name -> is_multi, for the capturing metavariables of one pattern."""
    out: dict[str, bool] = {}
    for multi, name in _METAVAR.findall(pattern):
        if name.startswith("_"):
            continue                       # `$_X` is ast-grep's non-capturing form
        out[name] = out.get(name, False) or bool(multi)
    return out


class _engine_errors:
    """Convert an `ast_grep_py` failure into this module's taxonomy.

    The engine is a Rust extension, and it does not confine itself to
    `Exception`. An unsupported language aborts with a pyo3
    `PanicException`, which inherits from **BaseException** — `except
    Exception` does not see it, and a panic would otherwise escape past the
    taxonomy and out of the caller's error handling entirely.

    Catching `BaseException` is deliberate and narrow: the three control-flow
    exceptions are re-raised untouched.
    """

    def __init__(self, what: str):
        self.what = what

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is None or isinstance(exc, PydantreeSitterError):
            return False
        if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
            return False
        raise PatternBuildError(
            f"{self.what}: {type(exc).__name__}: {exc}") from exc


def _load_engine():
    """Import `ast_grep_py`, or say which extra is missing.

    Imported inside the call, never at module import (§12): `from
    pydantree_sitter import Pattern` must work without the extra installed.
    """
    try:
        import ast_grep_py
    except ImportError as exc:
        raise PatternError(
            "pydantree_sitter.pattern needs the `pattern` extra: "
            "pip install 'pydantree-sitter[pattern]' "
            "(it installs ast-grep-py, which is not a base dependency)"
        ) from exc
    return ast_grep_py


# ---------------------------------------------------------------------------
# one parse, shared by every match of one call (§10)
# ---------------------------------------------------------------------------

class _Parse:
    """pydantree's own parse of the source, plus the lookup structures the
    handoff needs. Built once per `find_all` / `replace_all` call."""

    __slots__ = ("_by_range", "_exact", "data", "table", "text", "tree")

    @classmethod
    def of_tree(cls, text: str, tree) -> _Parse:
        """A `_Parse` around an ALREADY-parsed tree (the rewrite check has
        one in hand and must not parse the same text twice)."""
        self = cls.__new__(cls)
        self._init(text, tree)
        return self

    def __init__(self, language, text: str):
        self._init(text, language.parse(text.encode("utf-8")))

    def _init(self, text: str, tree) -> None:
        self.text = text
        self.data = text.encode("utf-8")
        self.tree = tree
        # O(len(text)), built once — never per match (§4.1 / Phase 0).
        self.table = char_to_byte_table(text)
        # (start_byte, end_byte, kind) -> node. The kind is part of the key on
        # purpose: several nodes can share one byte range (an
        # `expression_statement` wrapping its expression, say), and picking
        # one of them by position would be exactly the guess §4.1 forbids.
        self._exact: dict[tuple[int, int, str], tree_sitter.Node] = {}
        # (start_byte, end_byte) -> the kinds present, for the error message.
        self._by_range: dict[tuple[int, int], list[str]] = {}
        stack = [self.tree.root_node]
        while stack:
            node = stack.pop()
            key = (node.start_byte, node.end_byte)
            self._exact.setdefault((*key, node.type), node)
            self._by_range.setdefault(key, []).append(node.type)
            stack.extend(node.children)

    def to_bytes(self, rng) -> tuple[int, int]:
        """An `ast_grep_py` Range -> a byte range."""
        return self.table[rng.start.index], self.table[rng.end.index]

    def resolve(self, start: int, end: int, kind: str, *,
                pattern: str, agreement: str) -> tree_sitter.Node:
        """The node at EXACTLY this byte range and kind, or raise (§4.1).

        There is no fallback to the smallest enclosing node, and no warning
        followed by a best guess. A neighbouring node would let an extraction
        succeed and produce a wrong row, which is the one failure this
        project exists to prevent.
        """
        node = self._exact.get((start, end, kind))
        if node is not None:
            return node
        present = self._by_range.get((start, end))
        if present:
            raise PatternResolutionError(
                f"ast-grep reported node kind {kind!r} where pydantree's "
                f"grammar has {', '.join(repr(k) for k in present)}: the two "
                f"grammars disagree",
                start_byte=start, end_byte=end, pattern=pattern,
                nearest_kind=present[0], agreement=agreement)
        raise PatternResolutionError(
            "no node spans this byte range exactly in pydantree's tree: the "
            "two grammars disagree on node boundaries",
            start_byte=start, end_byte=end, pattern=pattern,
            nearest_kind=self._nearest(start, end), agreement=agreement)

    def _nearest(self, start: int, end: int) -> str | None:
        """The kind of the smallest node containing the range — DIAGNOSTIC
        ONLY. It is named in the error message and never returned as a
        match."""
        node = self.tree.root_node.descendant_for_byte_range(start, max(end - 1, start))
        return node.type if node is not None else None


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------

class Edit(BaseModel):
    """One byte-range replacement. Data — the module applies nothing to
    disk."""

    model_config = ConfigDict(frozen=True)

    start_byte: int
    end_byte: int
    new_text: str


class ReplaceResult(BaseModel):
    """The outcome of `replace_all`.

    `count` is the TRUE match count, taken before any edit is applied.
    `codeman`'s `expected_matches` contract depends on that (§8).
    """

    model_config = ConfigDict(frozen=True)

    count: int
    edits: tuple[Edit, ...]
    new_source: str
    agreement: str
    # What validation FOUND, whether or not it refused. With `validate=True`
    # a non-empty tuple is impossible — the first finding raised. With
    # `validate=False` this is the whole point: the caller gets the edits AND
    # the diagnosis, and decides for itself.
    diagnostics: tuple[str, ...] = ()
    # Matches dropped by the overlap policy (0 when it is "refuse").
    dropped_for_overlap: int = 0


class PatternMatch:
    """One pattern result: a span, a node in pydantree's own tree, and the
    metavariables it bound.

    Not a pydantic model, because it holds a live `tree_sitter.Node`. Use
    `.record` for the serializable form.
    """

    __slots__ = (
        "_agreement",
        "_language",
        "_parse",
        "captures",
        "node",
        "span",
    )

    def __init__(self, span: Span, node: tree_sitter.Node,
                 captures: dict[str, Any], parse: _Parse, agreement: str,
                 language):
        self.span = span
        self.node = node
        self.captures = captures
        self._parse = parse
        self._agreement = agreement
        self._language = language

    @property
    def text(self) -> str:
        return self.span.text

    @property
    def agreement(self) -> str:
        """The grammar-agreement digest this match was produced under."""
        return self._agreement

    def extract(self, model_cls, *, strict: bool = True) -> list:
        """Materialize `model_cls` with THIS match as the record (§10).

        The bridge between the two halves: ast-grep located the shape,
        pydantree types it. The node IS the record — the model's outer
        anchored path is not re-verified for it.

        The model must be a RECORD-mode model (`M(..., record=True)`), which
        is the only shape `Extractor.extract_tree_scoped` accepts. Note what
        that means in practice: pydantree's record mode is defined over
        key/value PAIR grammars (JSON, and authored pair shapes), so a
        Python `function_definition` is not a record and cannot be extracted
        this way. Use `.node` and `.captures` for grammars without a pair
        shape.
        """
        extractor = self._language.extractor(model_cls, strict=strict)
        if not extractor.compiled.spec.record:
            raise PatternError(
                f"{model_cls.__name__} is a FIELD-mode model; "
                f"PatternMatch.extract needs a record-mode model "
                f"(M(..., record=True)). A field-mode model carries an "
                f"anchored path over the whole tree, which is the opposite "
                f"of scoping extraction to one match.")
        return extractor.extract_tree_scoped(self.node, self._parse.tree)

    @property
    def record(self) -> dict:
        """The serializable form: spans as plain dicts, no live nodes."""
        return {
            "kind": self.node.type,
            "span": _span_dict(self.span),
            "captures": {
                name: ([_span_dict(s) for s in value]
                       if isinstance(value, tuple) else _span_dict(value))
                for name, value in self.captures.items()
            },
            "agreement": self._agreement,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return (f"PatternMatch({self.node.type!r} @ {self.span.line}:"
                f"{self.span.column}, captures={sorted(self.captures)})")


def _span_dict(span: Span) -> dict:
    return {
        "line": span.line, "column": span.column,
        "end_line": span.end_line, "end_column": span.end_column,
        "start_byte": span.start_byte, "end_byte": span.end_byte,
        "text": span.text,
    }


# ---------------------------------------------------------------------------
# Pattern
# ---------------------------------------------------------------------------

class Pattern:
    """A compiled ast-grep pattern or rule, bound to a Language.

        pat = Pattern("def $NAME($$$ARGS): $$$BODY", language=lang)
        pat = Pattern(Rule(pattern="$O.$M($$$A)", inside=Rule(kind="class_definition")),
                      language=lang)

    `Pattern` mirrors `Extractor`: **ALL checks run once, at construction** —
    the extra is installed, the language has an ast-grep grammar, every
    `kind` exists in the bound node-schema, and ast-grep itself accepts the
    rule. A built `Pattern` either works or it raised.

    Bind warnings are DATA on `.warnings`, surfaced once through
    `warnings.warn` at construction and never printed.
    """

    __slots__ = (
        "_agreement",
        "_arity",
        "_astgrep_name",
        "_engine",
        "_kwargs",
        "_language",
        "_rule",
        "_source",
        "warnings",
    )

    def __init__(self, pattern, *, language, astgrep_name: str | None = None):
        self._engine = _load_engine()
        self._language = language

        name = astgrep_name or getattr(language, "astgrep_name", None)
        if name is None:
            raise UnsupportedLanguageError(
                f"ast-grep has no grammar for language "
                f"{getattr(language, 'name', None)!r}. ast-grep compiles a "
                f"fixed language set into its wheel, so a grammar built by "
                f"pydantree-sitter-grammar has no counterpart there — this is "
                f"not a missing install. Known here: "
                f"{', '.join(sorted(_known_languages()))}. Pass "
                f"astgrep_name='...' if you know the correct identifier.")
        self._astgrep_name = name

        self._rule = pattern if isinstance(pattern, Rule) else Rule.of(pattern)
        self._source = self._rule.pattern or repr(self._rule.to_astgrep())

        # The highest-value check, and the cheapest: reject an unknown node
        # kind BY NAME, before any parser starts (§6).
        schema = getattr(language, "schema", None)
        if schema is not None:
            self._rule.check_kinds(schema)

        self._kwargs = self._rule.to_astgrep()
        self._arity = _metavar_arity(self._rule.pattern or "")

        # A bundle registered into ast-grep is the SAME artifact on both
        # sides, so agreement is by construction, not by measurement.
        if name in _REGISTERED and getattr(language, "astgrep_is_bundle", False):
            agreement = GrammarAgreement(
                language=name,
                astgrep_version=_dist_version("ast-grep-py"),
                grammar_dist=f"bundle:{_REGISTERED[name][0]}",
                grammar_version="same-artifact",
                tree_sitter_version=tree_sitter.__version__,
                verified=True, same_artifact=True)
        else:
            agreement = agreement_for(name)
        self._agreement = agreement
        self.warnings: tuple[str, ...] = agreement.warnings

        # Make ast-grep accept the rule AND the language NOW, not on the
        # first search. This is also where an unknown language surfaces: the
        # engine panics rather than raising, and `_engine_errors` converts it.
        with _engine_errors(f"ast-grep rejected the rule for language {name!r}"):
            self._engine.SgRoot("", name).root().find(**self._kwargs)

        if self.warnings:
            warnings.warn(
                "Pattern bind warnings:\n  " + "\n  ".join(self.warnings),
                stacklevel=2)

    # -- accessors ----------------------------------------------------------

    @property
    def rule(self) -> Rule:
        return self._rule

    @property
    def language(self):
        return self._language

    @property
    def agreement(self) -> GrammarAgreement:
        return self._agreement

    def metavariables(self) -> frozenset[str]:
        """The metavariables this pattern binds."""
        return self._rule.metavariables()

    # -- search -------------------------------------------------------------

    def find(self, source: str) -> PatternMatch | None:
        """The first match, or None."""
        for match in self.find_all(source):
            return match
        return None

    def find_all(self, source: str) -> tuple[PatternMatch, ...]:
        """Every match, in source order.

        One pydantree parse per call, shared by every match returned (§10),
        along with the one character-to-byte table.
        """
        parse = _Parse(self._language, source)
        return tuple(self._matches(source, parse))

    def _matches(self, source: str, parse: _Parse):
        digest = self._agreement.digest
        with _engine_errors(f"ast-grep failed on language {self._astgrep_name!r}"):
            root = self._engine.SgRoot(source, self._astgrep_name).root()
            found = list(root.find_all(**self._kwargs))
        for sg in found:
            start, end = parse.to_bytes(sg.range())
            node = parse.resolve(start, end, sg.kind(),
                                 pattern=self._source, agreement=digest)
            yield PatternMatch(Span.from_node(node), node,
                               self._resolve_captures(sg, parse, digest),
                               parse, digest, self._language)

    def _resolve_captures(self, sg, parse: _Parse, digest: str) -> dict[str, Any]:
        """Every metavariable, resolved to pydantree nodes by the same exact
        rule as the whole match.

        Captures are resolved as strictly as matches. Phase 0 measured them
        separately (7 663 captures, 0 failures) precisely because this is
        where two grammar revisions are most likely to diverge.
        """
        out: dict[str, Any] = {}
        for name, is_multi in self._arity.items():
            if is_multi:
                nodes = sg.get_multiple_matches(name)
                out[name] = tuple(
                    Span.from_node(self._resolve_one(n, parse, digest))
                    for n in nodes)
            else:
                got = sg.get_match(name)
                if got is None:
                    continue           # an optional metavariable bound nothing
                out[name] = Span.from_node(self._resolve_one(got, parse, digest))
        return out

    def _resolve_one(self, sg, parse: _Parse, digest: str) -> tree_sitter.Node:
        start, end = parse.to_bytes(sg.range())
        return parse.resolve(start, end, sg.kind(),
                             pattern=self._source, agreement=digest)

    # -- rewrite ------------------------------------------------------------

    def replace_all(self, source: str, template: str, *,
                    on_overlap: str = "refuse",
                    reindent: bool = False,
                    single_node: bool | None = None,
                    validate: bool = True) -> ReplaceResult:
        """Replace every match with `template`, and return the edits AS DATA.

        The template names metavariables the same way the pattern does:
        `$NAME` for one node, `$$$NAME` for a sequence. Expansion happens
        HERE and not in ast-grep — `ast_grep_py.SgNode.replace()` returns the
        template with its metavariables untouched (verified on 0.42.0 and
        0.45.3), unlike the `ast-grep` CLI. Doing it here also lets the
        template be checked against the rule's own metavariables first.

        The module writes no file, ever. `count` is the TRUE match count,
        taken before any edit, because `codeman`'s `expected_matches`
        contract depends on it. Edits apply right to left so earlier offsets
        stay valid.

        **on_overlap** — what to do when matches nest, as `$OBJ.$METHOD()`
        does over a chained call.

            "refuse"      raise. The default, and the right default: picking
                          one is a guess about intent.
            "outermost"   keep the widest match of each nest, drop the rest.
            "innermost"   keep the narrowest.

        **reindent** — prefix every line after the first of a replacement
        with the match's own leading indentation. Fixes MULTI-LINE TEMPLATES
        (`"if $C:\n    $$$B"` spliced at column 8 would otherwise indent its
        second line to column 4). It does NOT fix a collapsed body: a
        template that writes `: $$$BODY` genuinely asks for the body on the
        header line, and ast-grep's CLI collapses it identically.

        **validate / single_node** — see `_verify_reparse`.
        """
        if on_overlap not in ("refuse", "outermost", "innermost"):
            raise PatternRewriteError(
                f"on_overlap={on_overlap!r} is not one of 'refuse', "
                f"'outermost', 'innermost'.")

        unknown = sorted(metavariables_of(template) - self.metavariables())
        if unknown:
            raise PatternRewriteError(
                f"template names metavariable(s) "
                f"{', '.join('$' + n for n in unknown)} that the pattern does "
                f"not bind. The pattern binds: "
                f"{', '.join('$' + n for n in sorted(self.metavariables())) or '(none)'}.")

        parse = _Parse(self._language, source)
        matches = tuple(self._matches(source, parse))
        count = len(matches)

        kept = matches if on_overlap == "refuse" else _resolve_nesting(
            matches, outermost=on_overlap == "outermost")

        edits = tuple(
            Edit(start_byte=m.span.start_byte, end_byte=m.span.end_byte,
                 new_text=_expand(template, m, parse, reindent=reindent))
            for m in kept)

        if on_overlap == "refuse":
            _reject_overlap(edits)
        new_source = _apply(source, edits)

        diagnostics = self._verify_reparse(parse, new_source, edits,
                                           single_node=single_node,
                                           raising=validate)
        return ReplaceResult(count=count, edits=edits,
                             new_source=new_source,
                             agreement=self._agreement.digest,
                             diagnostics=diagnostics,
                             dropped_for_overlap=count - len(kept))

    def _verify_reparse(self, parse: _Parse, new_source: str,
                        edits: tuple[Edit, ...], *,
                        single_node: bool | None,
                        raising: bool) -> tuple[str, ...]:
        """Verify the rewrite. THREE tiers, weakest first.

        1. **tree-sitter (always).** No NEW parse error. Compared against the
           original, not against zero: source that already had a syntax
           error must still be rewritable.

        2. **the language's own parser (when the Language has one).** This is
           the check that actually works. tree-sitter's error recovery is
           weaker than a real parser and accepts source CPython rejects:

               def f(a): x = 1
                   return x

           `has_error` is False — tree-sitter reparents `return x` to MODULE
           level, out of the function — while CPython raises `SyntaxError`.
           Over this package's own source, tier 1 missed 19 of 19 broken
           rewrites and tier 2 caught all 19, rejecting none of the 35 valid
           ones. See `syntax.py`.

        3. **each edit site is one node (structural proxy).** Cheap and
           universal, but it OVER-refuses: a template that legitimately
           expands one statement into two is indistinguishable from a
           rewrite that leaked, because the difference is validity and
           tree-sitter cannot see validity.

           So tier 3 is not the default where tier 2 exists. `single_node`
           default None means AUTO: on when the Language has no
           `syntax_check`, off when it does. Pass True to force it, False to
           forbid it.

        `raising=False` (the caller's `validate=False`) turns every finding
        into a diagnostic string instead of an exception. The edits are
        returned either way — they are data — and the caller decides.
        """
        findings: list[str] = []

        new_tree = self._language.parse(new_source.encode("utf-8"))
        if _has_error(new_tree.root_node) and not _has_error(parse.tree.root_node):
            findings.append(
                "the rewrite produced source that does not parse: the "
                "original had no ERROR node and the result does.")

        check = getattr(self._language, "syntax_check", None)
        if check is not None and not findings:
            original_ok = _passes(check, parse.text)
            if original_ok and not _passes(check, new_source):
                findings.append(
                    f"the rewrite produced source the {self._astgrep_name} "
                    f"parser rejects: {_why(check, new_source)}. tree-sitter "
                    f"did NOT report this — its error recovery is weaker "
                    f"than the language's own parser.")

        use_single = single_node if single_node is not None else check is None
        if use_single and not findings:
            after = _Parse.of_tree(new_source, new_tree)
            for start, end, edit in _new_ranges(edits):
                if end <= start or after._by_range.get((start, end)):
                    continue
                findings.append(
                    f"the replacement at bytes {start}..{end} is not a single "
                    f"node in the result: it spans more than one, so the edit "
                    f"may have leaked into the surrounding code. Replacement "
                    f"text: {edit.new_text[:80]!r}")
                break

        if findings and raising:
            raise PatternRewriteError(
                findings[0] + " The edits are NOT applied. Pass "
                "validate=False to receive them with this as a diagnostic "
                "instead.")
        return tuple(findings)


def _known_languages() -> set[str]:
    from .agreement import AGREEMENT_RECORDS
    return set(AGREEMENT_RECORDS)


def _passes(check, source: str) -> bool:
    """Does `source` satisfy the language's own parser?

    Any exception counts as a rejection. A `SyntaxCheck` is allowed to raise
    whatever its parser raises — `SyntaxError`, `json.JSONDecodeError`, a
    library's own type — and this module does not enumerate them.
    """
    try:
        check(source)
    except Exception:  # noqa: BLE001 - a SyntaxCheck raises its parser's own type
        return False
    return True


def _why(check, source: str) -> str:
    try:
        check(source)
    except Exception as exc:  # noqa: BLE001 - see _passes
        return f"{type(exc).__name__}: {exc}"
    return "(no error)"


def _resolve_nesting(matches, *, outermost: bool):
    """Drop the matches nested inside a kept one (§8, `on_overlap`).

    Sorted so the preferred match of each nest comes first, then a linear
    sweep keeps a match only when it does not overlap one already kept.
    """
    ordered = sorted(
        matches,
        key=lambda m: (m.span.start_byte, -m.span.end_byte) if outermost
        else (m.span.start_byte, m.span.end_byte))
    if not outermost:
        ordered = sorted(matches, key=lambda m: (m.span.end_byte - m.span.start_byte))
    kept: list = []
    for match in ordered:
        if any(not (match.span.end_byte <= k.span.start_byte
                    or match.span.start_byte >= k.span.end_byte)
               for k in kept):
            continue
        kept.append(match)
    return sorted(kept, key=lambda m: m.span.start_byte)


def _has_error(root: tree_sitter.Node) -> bool:
    """Does this tree carry an ERROR or MISSING node?

    `has_error` on the root covers both, and it is a flag read rather than a
    walk."""
    return bool(root.has_error)


def _expand(template: str, match: PatternMatch, parse: _Parse, *,
            reindent: bool = False) -> str:
    """Substitute the match's metavariables into `template`.

    A `$$$NAME` sequence expands to the ORIGINAL source text spanning its
    first through last node, delimiters included. Joining the node texts with
    a guessed separator would drop the commas and the whitespace the caller
    wrote; taking the span reproduces them exactly.

    An unbound metavariable expands to the empty string. It reached here only
    because the pattern binds it, so it is an optional part that did not
    match — `$$$ARGS` of `f()` is the ordinary case.
    """
    def sub(hit: re.Match) -> str:
        name = hit.group(2)
        if name.startswith("_"):
            return hit.group(0)
        value = match.captures.get(name)
        if value is None:
            return ""
        if isinstance(value, tuple):
            if not value:
                return ""
            return parse.text[_char_of(parse, value[0].start_byte):
                              _char_of(parse, value[-1].end_byte)]
        return value.text
    text = _METAVAR.sub(sub, template)
    if reindent and "\n" in text:
        text = _reindent(text, _indent_of(parse, match.span.start_byte))
    return text


def _indent_of(parse: _Parse, start_byte: int) -> str:
    """The whitespace before `start_byte` on its own line."""
    char = _char_of(parse, start_byte)
    line_start = parse.text.rfind("\n", 0, char) + 1
    prefix = parse.text[line_start:char]
    return prefix if prefix.strip() == "" else ""


def _reindent(text: str, indent: str) -> str:
    """Prefix every line after the first with `indent`, leaving blank lines
    blank. The first line is spliced where the match already sat, so it needs
    no prefix."""
    if not indent:
        return text
    head, _, tail = text.partition("\n")
    lines = [indent + line if line.strip() else line
             for line in tail.split("\n")]
    return head + "\n" + "\n".join(lines)


def _char_of(parse: _Parse, byte: int) -> int:
    """Byte offset -> character offset, for slicing `parse.text`.

    The table is sorted, so this is a bisect rather than a scan."""
    import bisect
    return bisect.bisect_left(parse.table, byte)


def _new_ranges(edits: tuple[Edit, ...]):
    """Each edit's byte range IN THE RESULT, with the drift of the earlier
    edits applied. Ascending order, so the drift accumulates forward."""
    drift = 0
    for edit in sorted(edits, key=lambda e: e.start_byte):
        length = len(edit.new_text.encode("utf-8"))
        start = edit.start_byte + drift
        yield start, start + length, edit
        drift += length - (edit.end_byte - edit.start_byte)


def _reject_overlap(edits: tuple[Edit, ...]) -> None:
    """Refuse overlapping edits (§8).

    Overlap means the pattern matched nested occurrences — `$A.$B($$$C)` over
    a chained call is the everyday example. Refusing is the correct
    behaviour: picking one of them is a guess about intent, and this module
    does not guess. The caller narrows the rule.
    """
    ordered = sorted(edits, key=lambda e: (e.start_byte, e.end_byte))
    for before, after in pairwise(ordered):
        if after.start_byte < before.end_byte:
            raise PatternRewriteError(
                f"overlapping edits at bytes {before.start_byte}.."
                f"{before.end_byte} and {after.start_byte}..{after.end_byte}: "
                f"the pattern matched nested occurrences. Narrow the rule "
                f"(add `not`, `inside`, or a `kind`) — this module refuses "
                f"rather than picking one.")


def _apply(source: str, edits: tuple[Edit, ...]) -> str:
    """Apply edits right to left, so earlier offsets stay valid.

    Byte offsets over UTF-8 throughout: the source is encoded once, spliced,
    and decoded once. Slicing the `str` by byte offsets would be wrong the
    moment the source holds a non-ASCII character.
    """
    data = source.encode("utf-8")
    for edit in sorted(edits, key=lambda e: e.start_byte, reverse=True):
        data = (data[:edit.start_byte]
                + edit.new_text.encode("utf-8")
                + data[edit.end_byte:])
    return data.decode("utf-8")
