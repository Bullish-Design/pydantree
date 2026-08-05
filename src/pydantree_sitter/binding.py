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
from .errors import ShapeError
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


def _transient_language(lang: "Language", schema=None) -> "Language":
    """A copy of `lang` with an explicit schema (the sugar path)."""
    return Language(lang._lang, schema=schema if schema is not None
                    else lang._schema, value_map=lang._value_map)


# memoized per-input Language for the sugar path (A2/REVIEW 018):
# `Model.extract(text, language=module)` used to build a FRESH Language per
# call, silently re-running every check and recompiling every query — the
# documented one-liner was the pathological path. Weak keys: the module /
# tree_sitter.Language / callable stays alive, the Language dies with it.
# Inputs that are neither hashable nor weak-referenceable simply skip the
# cache (the TypeError is the signal, not an error).
_LANGUAGE_CACHE: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _language_for(language):
    """Normalize the sugar `language=` argument: None | Language | module |
    tree_sitter.Language -> Language or None. Memoized per input (the
    explicit-`schema=` route builds a transient copy AFTER this and stays
    uncached)."""
    if language is None:
        return None
    if isinstance(language, Language):
        return language
    try:
        cached = _LANGUAGE_CACHE.get(language)
    except TypeError:
        cached = None                     # unhashable/unweakable input
    if cached is not None:
        return cached
    lang, schema = _resolve_language(language)
    built = Language(lang, schema=schema)
    try:
        _LANGUAGE_CACHE[language] = built
    except TypeError:
        pass
    return built


# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------

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

    __slots__ = ("_lang", "_schema", "_value_map", "_lib", "_extractors")

    def __init__(self, lang, schema=None, value_map=None):
        if isinstance(lang, Language):
            # wrapping another Language carries its schema AND value map
            # (the ONE Language-unwrap owner; _resolve_language handles the
            # rest of the input family)
            if schema is None:
                schema = lang._schema
            if value_map is None:
                value_map = lang._value_map
            lang = lang._lang
        raw, schema = _resolve_language(lang, schema)
        self._lang = raw
        self._schema = schema
        self._value_map = value_map
        self._lib = None
        self._extractors: dict = {}

    # -- construction -------------------------------------------------------

    @classmethod
    def load(cls, lang, schema=None, *, value_map=None) -> "Language":
        """Wrap a language (module / tree_sitter.Language / capsule)."""
        return cls(lang, schema=schema, value_map=value_map)

    @classmethod
    def from_module(cls, mod, schema=None, value_map=None) -> "Language":
        """A grammar module (e.g. tree_sitter_python) as a Language."""
        return cls(mod, schema=schema, value_map=value_map)

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
        """Incremental reparse (the 0.26 API, wrapped): `Parser.parse(new
        source, old_tree)` — the binding applies the edits internally from
        the old tree's positions. The old `old_source=` parameter is deleted
        (F-A11)."""
        if isinstance(source, str):
            source = source.encode("utf-8")
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
