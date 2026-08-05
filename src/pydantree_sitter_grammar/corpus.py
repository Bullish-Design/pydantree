"""pydantree_sitter_grammar.corpus — the corpus-testing harness (CONCEPT §4.8, Phase 5).

The systematic guard for the Phase-3 §4 semantic-intent leak: a conflict-free
grammar can still parse *wrongly* (a wrong ladder order generates clean but
flips `-a ^ b` to `(-a)^b`). Authors write `(source, expected-sexp)` cases;
the harness builds the grammar, parses each case, renders the CST, and diffs
against the expectation — at author time, before the grammar ships.

Rendering has a documented normalization story (the anonymous-node decision):

  * ``style="sexp"`` (default) — tree-sitter-canonical::

        (source_file (entry key: (identifier) '=' value: (integer)))

    Anonymous tokens are kept as ``'text'``. They ARE semantic: the operator
    is what distinguishes ``1 + 2`` from ``1 - 2``, so dropping them would
    make unrelated parses compare equal. This matches how tree-sitter's own
    corpus tests are written.
  * ``anonymous="drop"`` — shape-only: anonymous tokens are skipped. Use when
    the token set is irrelevant to the semantics under test.
  * ``style="compact"`` — the Phase-3A semantic-smoke format (``expr`` nodes
    render as bare parens, other named nodes as ``kind(...)``).
    ``pydantree_sitter_grammar.expressions.semantic_smoke`` delegates here — no parallel
    machinery.

Snapshotting: ``Corpus.run(..., snapshots_dir=...)`` writes the built
``grammar.json`` + ``node-schema.json`` beside the corpus so grammar changes
show up as reviewable diffs (the CONCEPT §4.8 promise).

Cases are ``corpus_case(source, expected, ...)`` (definition site recorded for
failure reports) or plain ``(source, expected)`` tuples.
"""

from __future__ import annotations

import difflib
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .builder import Grammar

# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusCase:
    """One (source, expected-sexp) case. `selector` renders the FIRST node of
    that type in DFS order instead of the tree root (the smoke corpus renders
    the outermost `expr`); `line` is the definition site (file:lineno)."""

    source: str
    expected: str
    name: str | None = None
    selector: str | None = None
    line: str | None = None


def corpus_case(source: str, expected: str, *, name: str | None = None,
                selector: str | None = None) -> CorpusCase:
    """A corpus case with its definition site recorded (for failure reports:
    `case <name> at file:lineno`)."""
    frame = inspect.currentframe()
    site = None
    if frame is not None and frame.f_back is not None:
        f = frame.f_back
        site = f"{inspect.getsourcefile(f) or '?'}:{f.f_lineno}"
    return CorpusCase(source=source, expected=expected, name=name,
                      selector=selector, line=site)


def _coerce_case(c) -> CorpusCase:
    if isinstance(c, CorpusCase):
        return c
    if isinstance(c, (tuple, list)) and len(c) == 2 \
            and all(isinstance(x, str) for x in c):
        return CorpusCase(source=c[0], expected=c[1])
    raise TypeError(
        f"corpus case must be corpus_case(...) or (source, expected) tuple, "
        f"got {c!r}")


# ---------------------------------------------------------------------------
# the CST renderers (the normalization story lives here)
# ---------------------------------------------------------------------------

def _quote(text: str) -> str:
    """Anonymous tokens render as 'text' (tree-sitter corpus canonical)."""
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _render_sexp(node, parts, *, anonymous: str, fields: bool) -> None:
    if not node.is_named:
        if anonymous == "keep":
            parts.append(_quote(node.type))
        return
    parts.append("(")
    parts.append(node.type)
    rendered: list[str] = []
    for i, c in enumerate(node.children):
        sub: list[str] = []
        _render_sexp(c, sub, anonymous=anonymous, fields=fields)
        if not sub:
            continue  # anonymous="drop" renders nothing -> no stray space
        s = "".join(sub)
        if fields:
            fname = node.field_name_for_child(i)
            if fname:
                s = fname + ": " + s
        rendered.append(s)
    if rendered:
        parts.append(" " + " ".join(rendered))
    parts.append(")")


def render(node, *, anonymous: str = "keep", fields: bool = True) -> str:
    """Render a CST node as a single-line sexp.

    Default (`anonymous="keep"`, `fields=True`) is tree-sitter-canonical:
    named nodes + field labels + anonymous tokens as 'text'. `anonymous`
    may be "keep" or "drop".
    """
    if anonymous not in ("keep", "drop"):
        raise ValueError(f"anonymous must be 'keep' or 'drop', got {anonymous!r}")
    parts: list[str] = []
    _render_sexp(node, parts, anonymous=anonymous, fields=fields)
    return "".join(parts)


def render_compact(n, *, expr_kind: str = "expr") -> str:
    """The Phase-3A semantic-smoke format (pins expression semantics):

    `expr_kind` nodes render as bare parens, other named nodes as
    `kind(...)`, anonymous tokens as their text, hidden `_` rules by name.
    `-a ^ b` renders `(- ((identifier) ^ (identifier)))`; `-f(x)` renders
    `(- ((identifier) ( args((identifier)) )))` — the renderer walks the
    first expression node, so a ladder reorder that flips the tree shape
    shows up as a diff.
    """
    if not n.is_named:
        return n.type
    if n.type.startswith("_"):
        return n.type
    if n.child_count == 0:
        return n.type
    inner = " ".join(render_compact(c, expr_kind=expr_kind) for c in n.children)
    return f"({inner})" if n.type == expr_kind else f"{n.type}({inner})"


# ---------------------------------------------------------------------------
# the corpus + runner
# ---------------------------------------------------------------------------


@dataclass
class CorpusFailure:
    """One failing case: what was expected vs what the grammar produced."""

    case: CorpusCase
    got: str | None            # the rendered CST (None = no parseable node)
    detail: str = ""

    def message(self, style: str) -> str:
        where = self.case.line or self.case.name or f"case #{self.case.source!r}"
        if self.got is None:
            return f"case {self.case.source!r} ({where}): {self.detail}"
        return (
            f"case {self.case.source!r} ({where}): shape {self.got!r}, "
            f"expected {self.case.expected!r} "
            f"({self.detail or 'a grammar change altered the parse'})")


@dataclass
class CorpusResult:
    """The run outcome: per-case failures + the snapshot paths."""

    cases: list[CorpusCase]
    failures: list[CorpusFailure] = field(default_factory=list)
    snapshots: list[Path] = field(default_factory=list)
    style: str = "sexp"

    def ok(self) -> bool:
        return not self.failures

    def report(self, *, diff: bool = True) -> str:
        lines = [f"corpus: {len(self.cases)} case(s), "
                 f"{len(self.failures)} failure(s)"]
        if self.snapshots:
            lines.append("  snapshots: " + ", ".join(str(p) for p in self.snapshots))
        if not self.failures:
            return "\n".join(lines)
        for f in self.failures:
            lines.append("  - " + f.message(self.style))
            if diff and f.got is not None:
                d = difflib.unified_diff(
                    [f.case.expected + "\n"], [f.got + "\n"],
                    fromfile="expected", tofile="got", lineterm="")
                lines.append("      " + "\n      ".join(
                    line.rstrip("\n") for line in d))
        return "\n".join(lines)


class Corpus:
    """An author's `(source, expected-sexp)` test set for one grammar.

    ``run()`` builds the grammar (or reuses a BuildResult), parses each case,
    renders the CST and compares. With ``snapshots_dir``, the built
    grammar.json + node-schema.json are written beside the corpus so grammar
    changes produce reviewable diffs.
    """

    def __init__(self, cases: Iterable, *, name: str | None = None,
                 anonymous: str = "keep", style: str = "sexp",
                 selector: str | None = None,
                 snapshots_dir: str | Path | None = None):
        if style not in ("sexp", "compact"):
            raise ValueError(f"style must be 'sexp' or 'compact', got {style!r}")
        self.name = name
        self.cases = [_coerce_case(c) for c in cases]
        self.anonymous = anonymous
        self.style = style
        self.selector = selector
        self.snapshots_dir = Path(snapshots_dir) if snapshots_dir is not None else None

    # -- the runner --------------------------------------------------------

    def run(self, build_result=None, grammar: Grammar | None = None, *,
            cache_dir=None) -> CorpusResult:
        """Parse every case against a built grammar and diff the CSTs.

        Builds `grammar` (a pydantree_sitter_grammar builder Grammar) via the pipeline, or
        reuses `build_result` (a BuildResult). Returns a CorpusResult; the
        author-facing report is `result.report()` (empty failures = pass).
        """
        if build_result is None:
            if grammar is None:
                raise ValueError("run() needs a grammar= or build_result=")
            from .pipeline import build_builder
            build_result = build_builder(grammar, cache_dir=cache_dir)
        from .language import load_language
        lang, _lib = load_language(build_result.so_path)

        snapshots: list[Path] = []
        if self.snapshots_dir is not None:
            out = self.snapshots_dir
            out.mkdir(parents=True, exist_ok=True)
            if build_result.grammar_json.exists():
                snapshots.append(_snapshot(build_result.grammar_json, out / "grammar.json"))
            if build_result.node_schema_json is not None \
                    and build_result.node_schema_json.exists():
                snapshots.append(_snapshot(build_result.node_schema_json,
                                           out / "node-schema.json"))

        failures: list[CorpusFailure] = []
        for case in self.cases:
            tree = _parse(lang, case.source)
            root = tree.root_node
            target = _select(root, case.selector or self.selector)
            if target is None:
                failures.append(CorpusFailure(
                    case, None,
                    detail=f"no {case.selector or self.selector or 'root'} node "
                           f"found (parse errors: {_first_error(tree, case.source)})"))
                continue
            got = render_compact(target) if self.style == "compact" \
                else render(target, anonymous=self.anonymous)
            if got != case.expected:
                failures.append(CorpusFailure(case, got))
        return CorpusResult(cases=self.cases, failures=failures,
                            snapshots=snapshots, style=self.style)


def _snapshot(src: Path, dst: Path) -> Path:
    import shutil
    shutil.copyfile(src, dst)
    return dst


# ---------------------------------------------------------------------------
# parse helpers (shared with expressions.semantic_smoke)
# ---------------------------------------------------------------------------

def _parse(lang, source: str):
    import tree_sitter
    return tree_sitter.Parser(lang).parse(source.encode("utf-8"))


def _select(node, selector: str | None):
    """The node to render: the tree root, or the FIRST node of `selector`
    type in DFS order (the outermost occurrence)."""
    if selector is None:
        return node
    if node.type == selector:
        return node
    for c in node.children:
        found = _select(c, selector)
        if found is not None:
            return found
    return None


def _first_error(tree, source: str) -> str:
    out: list[str] = []

    def walk(n):
        if n.type == "ERROR" or n.is_missing:
            out.append(f"{n.type}@{source[n.start_byte:n.end_byte]!r}")
        for c in n.children:
            walk(c)
    walk(tree.root_node)
    return ", ".join(out) or "none"
