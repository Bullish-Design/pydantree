"""pydantree_sitter.binding — Language + Extractor: the explicit bind (014 §4.2).

`lang.extractor(Model)` runs ALL checks once; the compiled state lives on
the Language instance, keyed by (model class, strict) — correct identity by
construction (no class-level compiled caches, no global registry, D5).
`Model.extract(text, language=...)` is sugar over this.

Warnings are DATA (`Extractor.warnings`) surfaced once via warnings.warn at
bind — never prints (F-A6).
"""

from __future__ import annotations

import types
import warnings
import weakref
from pathlib import Path

import tree_sitter

from .compiler import compile_spec
from .errors import BundleError, ShapeError
from .loader import load_bundle
from .materialize import _record_kwargs, extract_field, extract_record
from .schema import NodeSchema
from .spec import OutputModel
from .valuemap import (
    JSON_VALUE_MAP,
    ValueMap,
    looks_like_json,
)

__all__ = ["Language", "Extractor"]


# ---------------------------------------------------------------------------
# language resolution
# ---------------------------------------------------------------------------

def _resolve_language(language, schema=None):
    """Normalize (tree_sitter.Language | module | callable | capsule) ->
    (tree_sitter.Language, schema_or_None). Language-wrapping-Language is
    handled by `Language.__init__` (the ONE unwrap owner — it must also
    inherit the value map, which this function doesn't know about)."""
    if isinstance(language, tree_sitter.Language):
        lang = language
    elif callable(language):                   # tree_sitter_python.language
        lang = tree_sitter.Language(language())
    elif hasattr(language, "language") and callable(language.language):
        lang = tree_sitter.Language(language.language())
    else:
        lang = tree_sitter.Language(language)  # a bare PyCapsule
    if schema is not None:
        schema = _load_schema(schema)
    return lang, schema


def _load_schema(schema):
    """NodeSchema | path | dict -> NodeSchema (the schema IS the byproduct;
    the only load path is from_node_types_json)."""
    if isinstance(schema, NodeSchema):
        return schema
    if isinstance(schema, (str, Path)):
        return NodeSchema.from_node_types_json(schema)
    if isinstance(schema, dict):
        return NodeSchema.from_list(schema.get("node_types", schema))
    raise TypeError(f"cannot build a node-schema from {type(schema)!r}")


# ---------------------------------------------------------------------------
# ast-grep language resolution (022 §7)
# ---------------------------------------------------------------------------

# ast-grep compiles a fixed language set into its wheel; pydantree builds any
# grammar. The two sets are not the same, and the mismatch must be explicit.
# This map covers only the languages project 022 ships with a grammar
# agreement record — it is the DEFAULT, and an explicit `astgrep_name=` or a
# bundle metadata key always wins.
_ASTGREP_NAMES = {
    "python": "python",
}


def _default_astgrep_name(lang: tree_sitter.Language) -> str | None:
    """Guess the ast-grep language id from a tree_sitter.Language.

    `tree_sitter.Language.name` is None for some grammar wheels
    (`tree_sitter_json` is one), so this returns None often. None is not a
    failure here — it means `Pattern` must be told the name explicitly, and
    `UnsupportedLanguageError` says so.
    """
    name = lang.name
    if not name:
        return None
    return _ASTGREP_NAMES.get(name.lower())


def _transient_language(lang: "Language", schema=None) -> "Language":
    """A copy of `lang` with an explicit schema (the sugar path)."""
    return Language(lang._lang, schema=schema if schema is not None
                    else lang._schema, value_map=lang._value_map,
                    astgrep_name=lang._astgrep_name,
                    syntax_check=lang._syntax_check)


# memoized per-input Language for the sugar path (A2/REVIEW 018):
# `Model.extract(text, language=module)` used to build a FRESH Language per
# call, silently re-running every check and recompiling every query — the
# documented one-liner was the pathological path. Weak keys: the module /
# tree_sitter.Language / callable stays alive, the Language dies with it.
# Inputs that are neither hashable nor weak-referenceable simply skip the
# cache (the TypeError is the signal, not an error).
_LANGUAGE_CACHE: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
# WeakKeyDictionary is not thread-safe; the sugar path can race from two
# threads (REVIEW 020 minor — the caches were unsynchronized).
_LANGUAGE_LOCK = __import__("threading").Lock()


def _language_for(language):
    """Normalize the sugar `language=` argument: None | Language | module |
    tree_sitter.Language -> Language or None. Memoized per input (the
    explicit-`schema=` route builds a transient copy AFTER this and stays
    uncached)."""
    if language is None:
        return None
    if isinstance(language, Language):
        return language
    with _LANGUAGE_LOCK:
        try:
            cached = _LANGUAGE_CACHE.get(language)
        except TypeError:
            cached = None                     # unhashable/unweakable input
        if cached is not None:
            return cached
    lang, schema = _resolve_language(language)
    built = Language(lang, schema=schema)
    try:
        with _LANGUAGE_LOCK:
            _LANGUAGE_CACHE[language] = built
    except TypeError:
        pass
    return built


# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------

def _point_of(text: bytes, byte: int) -> tuple:
    """The (row, column) of a byte offset (tree-sitter edit points)."""
    row = text.count(b"\n", 0, byte)
    last_nl = text.rfind(b"\n", 0, byte)
    return (row, byte - (last_nl + 1))


def _apply_edit(tree: tree_sitter.Tree, old_text: bytes, new_text: bytes) -> None:
    """Apply the old_text -> new_text diff to `tree` before reparsing: the
    tree-sitter edit protocol requires telling the tree EXACTLY what changed
    (start/end byte offsets + points); without it, `Parser.parse(new_source,
    old_tree)` reuses the old tree's nodes at their recorded offsets and
    mid-buffer edits produce silently wrong trees (A3/REVIEW 020)."""
    start = 0
    limit = min(len(old_text), len(new_text))
    while start < limit and old_text[start] == new_text[start]:
        start += 1
    old_end = len(old_text)
    new_end = len(new_text)
    while old_end > start and new_end > start \
            and old_text[old_end - 1] == new_text[new_end - 1]:
        old_end -= 1
        new_end -= 1
    tree.edit(start, old_end, new_end,
              _point_of(old_text, start),
              _point_of(old_text, old_end),
              _point_of(new_text, new_end))


class Language:
    """A tree_sitter.Language + an optionally-bound node-schema + ValueMap.

        lang = Language.load_bundle("bundles/mylang")
        lang = Language.from_module(tree_sitter_python, schema=...)
        lang = Language.load(tree_sitter_python.language(), schema=...)

    `extractor(Model)` runs all checks once and caches the Extractor on THIS
    instance keyed by (model, strict) — a second bind against another
    language re-checks (F-A1's silent cross-language cache is impossible
    here by construction).
    """

    __slots__ = ("_lang", "_schema", "_value_map", "_lib", "_extractors",
                 "_astgrep_name", "_patterns", "_syntax_check",
                 "_bundle_path", "_bundle_symbol")

    def __init__(self, lang, schema=None, value_map=None, astgrep_name=None,
                 syntax_check=None):
        if isinstance(lang, Language):
            # wrapping another Language carries its schema AND value map
            # (the ONE Language-unwrap owner; _resolve_language handles the
            # rest of the input family)
            if schema is None:
                schema = lang._schema
            if value_map is None:
                value_map = lang._value_map
            if astgrep_name is None:
                astgrep_name = lang._astgrep_name
            if syntax_check is None:
                syntax_check = lang._syntax_check
            lang = lang._lang
        raw, schema = _resolve_language(lang, schema)
        self._lang = raw
        self._schema = schema
        self._value_map = value_map
        self._lib = None
        self._extractors: dict = {}
        # 022 §7 resolution order: explicit argument, then bundle metadata
        # (set by `load_bundle`), then the built-in map.
        self._astgrep_name = astgrep_name
        # 022 follow-up: the third-parser seam. An explicit check wins; the
        # `syntax_check` property falls back to the registry.
        self._syntax_check = syntax_check
        # set by load_bundle: what `register_astgrep` needs to hand ast-grep
        self._bundle_path = None
        self._bundle_symbol = None
        # compiled Patterns, cached on THIS instance exactly as `_extractors`
        # is — a Pattern is bound to one Language and can never leak to
        # another (the F-A1 argument, applied to patterns).
        self._patterns: dict = {}

    # -- construction -------------------------------------------------------

    @classmethod
    def load(cls, lang, schema=None, *, value_map=None,
             astgrep_name=None, syntax_check=None) -> "Language":
        """Wrap a language (module / tree_sitter.Language / capsule)."""
        return cls(lang, schema=schema, value_map=value_map,
                   astgrep_name=astgrep_name, syntax_check=syntax_check)

    @classmethod
    def from_module(cls, mod, schema=None, value_map=None,
                    astgrep_name=None, syntax_check=None) -> "Language":
        """A grammar module (e.g. tree_sitter_python) as a Language."""
        return cls(mod, schema=schema, value_map=value_map,
                   astgrep_name=astgrep_name, syntax_check=syntax_check)

    @classmethod
    def load_bundle(cls, dir, *, value_map=None) -> "Language":
        """Consume a packaged grammar bundle in ONE call (grammar.so +
        node-schema.json + metadata via the shared loader). Keeps the
        bundle's .so library alive for the language's lifetime (F-A10).
        A bundle `value_map` metadata entry becomes the Language's ValueMap;
        an explicit `value_map=` argument wins.
        """
        bundle = load_bundle(dir)
        lang = cls(bundle.language, schema=bundle.schema)
        lang._lib = bundle.lib
        if value_map is not None:
            lang._value_map = value_map
        elif bundle.metadata.get("value_map"):
            lang._value_map = ValueMap.model_validate(bundle.metadata["value_map"])
        # 022 §7: a bundle may declare which ast-grep grammar it corresponds
        # to. Most custom grammars have no counterpart and leave this unset.
        lang._astgrep_name = bundle.metadata.get("astgrep_name")
        # The artifact, for `register_astgrep`. The .so's export symbol is
        # `tree_sitter_<name>`; the file is renamed on packaging, so the
        # metadata is the only source for both.
        lang._bundle_path = bundle.path / bundle.metadata.get("artifact", "grammar.so")
        lang._bundle_symbol = f"tree_sitter_{bundle.metadata['name']}"
        return lang

    # -- accessors ----------------------------------------------------------

    @property
    def schema(self):
        return self._schema

    @property
    def value_map(self):
        return self._value_map

    @property
    def name(self) -> str:
        return self._lang.name

    @property
    def language(self) -> tree_sitter.Language:
        return self._lang

    @property
    def astgrep_name(self) -> str | None:
        """The ast-grep language identifier, or None when ast-grep has no
        grammar for this Language (022 §7).

        None is the answer for every grammar built by
        `pydantree-sitter-grammar`, and for a wheel whose
        `tree_sitter.Language.name` is None. `Pattern` turns it into
        `UnsupportedLanguageError`; pass `astgrep_name=` to override.
        """
        if self._astgrep_name is not None:
            return self._astgrep_name
        return _default_astgrep_name(self._lang)

    @property
    def astgrep_is_bundle(self) -> bool:
        """Did this Language come from a bundle whose .so ast-grep can load?"""
        return self._bundle_path is not None

    def register_astgrep(self, name: str | None = None, *, extensions=None,
                         meta_var_char: str | None = None,
                         expando_char: str | None = None) -> str:
        """Register THIS bundle's grammar with ast-grep, and use it.

            lang = Language.load_bundle("bundles/obsidian")
            lang.register_astgrep()
            pat = Pattern(Rule(kind="wiki_link"), language=lang)

        ast-grep then parses with the same shared library pydantree does, so
        the two cannot disagree about node kinds or byte ranges — §4's
        divergence risk does not exist for such a Language, and its
        `GrammarAgreement` is `verified` with `same_artifact=True`.

        Returns the registered name and sets `astgrep_name` to it.
        Registration is process-global (ast-grep's design); re-registering a
        name with a different artifact raises.
        """
        if self._bundle_path is None:
            raise BundleError(
                "register_astgrep() needs a Language built by "
                "Language.load_bundle(): ast-grep loads the bundle's "
                "grammar.so directly, and a Language wrapping a wheel has no "
                "such file to hand it.")
        from .pattern import register_bundle_language
        name = name or f"{self._lang.name or 'grammar'}"
        registered = register_bundle_language(
            name, self._bundle_path, self._bundle_symbol,
            extensions=extensions, meta_var_char=meta_var_char,
            expando_char=expando_char)
        self._astgrep_name = registered
        return registered

    @property
    def syntax_check(self):
        """The language's own validity check, or None (022 follow-up).

        A `SyntaxCheck` is `Callable[[str], None]` that RAISES on invalid
        source. `pattern.py` uses it to verify a rewrite, because
        tree-sitter's `has_error` is weaker than a real parser and accepts
        source the language rejects.

        Resolution: an explicit `syntax_check=` argument, then
        `syntax.SYNTAX_CHECKS` keyed by `astgrep_name`. Pass
        `syntax_check=False` to DISABLE the registry lookup and run without
        a language parser — the rewrite verifier then falls back to its
        structural proxy.
        """
        if self._syntax_check is False:
            return None
        if self._syntax_check is not None:
            return self._syntax_check
        from .syntax import syntax_check_for
        return syntax_check_for(self.astgrep_name)

    # -- binding ------------------------------------------------------------

    def extractor(self, model_cls, *, strict: bool = True) -> "Extractor":
        """Bind `model_cls`: ALL checks run here, once; the Extractor is
        cached on SELF keyed by (model_cls, strict)."""
        key = (model_cls, strict)
        ext = self._extractors.get(key)
        if ext is None:
            ext = Extractor(model_cls, self, strict=strict)
            self._extractors[key] = ext
        return ext

    # -- parsing ------------------------------------------------------------

    def parse(self, source: str | bytes) -> tree_sitter.Tree:
        if isinstance(source, str):
            source = source.encode("utf-8")
        return tree_sitter.Parser(self._lang).parse(source)

    def reparse(self, old_tree: tree_sitter.Tree,
                source: str | bytes) -> tree_sitter.Tree:
        """Incremental reparse: compute the old->new diff, apply
        `old_tree.edit(...)`, then `Parser.parse(new_source, old_tree)`.

        tree-sitter does NOT diff automatically — without `edit()` a
        mid-buffer change reuses the old tree's nodes at shifted offsets and
        the result is SILENTLY wrong (A3/REVIEW 020). The old text is
        recovered from the tree's root node (the parse retained it), so no
        `old_source=` parameter is needed; if it cannot be recovered the
        edit is skipped (the pre-fix behavior, correct for EOF appends).
        The old `old_source=` parameter was deleted (F-A11)."""
        if isinstance(source, str):
            source = source.encode("utf-8")
        old_text = old_tree.root_node.text
        if old_text is not None and old_text != source:
            _apply_edit(old_tree, old_text, source)
        return tree_sitter.Parser(self._lang).parse(source, old_tree)


# ---------------------------------------------------------------------------
# value-map resolution (014 §4.4)
# ---------------------------------------------------------------------------

def resolve_value_map(model_cls, language: Language) -> ValueMap:
    """Resolution order: explicit `value_map=` arg (Language.value_map, from
    a bundle's `value_map` entry) → JSON_VALUE_MAP iff the schema looks
    JSON-family (exact kind-set check, not a name regex) → else a bind-time
    ShapeError telling the user to run `propose_value_map` and pass the
    result. Schema-less record mode = JSON_VALUE_MAP + the documented JSON
    kinds. Field-mode models never need a map (the error only fires for
    record mode over a non-JSON grammar)."""
    spec = model_cls._match_spec
    if language.value_map is not None:
        return language.value_map
    schema = language.schema
    if schema is None:
        return JSON_VALUE_MAP
    if spec.record and not looks_like_json(schema):
        raise ShapeError(
            f"record mode over grammar {schema.name or '?'} needs a "
            f"ValueMap: the schema is not the JSON family. Run "
            f"propose_value_map(schema) and pass the reviewed result — "
            f"e.g. Language.load(..., schema=schema, value_map=vm) or a "
            f"bundle `value_map` metadata entry. (Value shapes are declared "
            f"data, never silent name-regex inference.)")
    return JSON_VALUE_MAP


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class Extractor:
    """A bound model: the compiled state + the extraction entry points.

        ext = lang.extractor(Assignment)     # all checks run here, once
        rows = ext.extract(text)             # no hidden state anywhere
    """

    def __init__(self, model: type, language: Language, *, strict: bool):
        self.model = model
        self.language = language
        self.strict = strict
        vm = resolve_value_map(model, language)
        self.compiled = compile_spec(model, language, value_map=vm)
        self.warnings: tuple = tuple(getattr(model, "_binding_warnings", ()))
        if self.warnings:
            warnings.warn(
                f"{model.__name__} bind warnings:\n  "
                + "\n  ".join(self.warnings),
                stacklevel=3)

    # -- diagnostics --------------------------------------------------------

    @property
    def query_source(self) -> str:
        """The emitted (or raw) .scm — diagnostics only."""
        return self.compiled.query_source

    # -- extraction ---------------------------------------------------------

    def extract(self, text) -> list:
        if not isinstance(text, bytes):
            text = text.encode("utf-8")
        tree = self.language.parse(text)
        return self.extract_tree(tree)

    def extract_tree(self, tree: tree_sitter.Tree) -> list:
        if self.compiled.spec.record:
            return extract_record(self.model, self.compiled, tree,
                                  strict=self.strict)
        return extract_field(self.model, self.compiled, tree,
                             strict=self.strict)

    def extract_tree_scoped(self, node: tree_sitter.Node,
                            tree: tree_sitter.Tree) -> list:
        """Record-mode materialization with `node` AS the record (nested
        sub-extractors): the value node IS the record — the outer anchored
        path is not re-verified for it (F-A2: one compiler, the nested
        model's inner query runs anchored at the value node)."""
        kwargs = _record_kwargs(self.model, self.compiled, node, tree)
        if kwargs is None:
            return []
        return [self.model(**kwargs)]

    def __repr__(self) -> str:  # pragma: no cover
        return (f"Extractor({self.model.__name__} over "
                f"{self.language.name!r})")
