"""The small generated-grammar runtime seam.

The grammar object owns a loaded tree-sitter language, its required schema,
and the generated typed namespace.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import tree_sitter

from .errors import BundleError, SchemaDriftError
from .find import find_in
from .generate import build_namespace
from .nodes import Node
from .schema import NodeSchema, load_schema

__all__ = ["Grammar", "Tree"]


def _language(value: Any) -> tree_sitter.Language | None:
    if value in (None, ""):
        return None
    if isinstance(value, tree_sitter.Language):
        return value
    if isinstance(value, str):
        value = importlib.import_module(value)
    if hasattr(value, "language") and callable(value.language):
        value = value.language()
    elif callable(value):
        value = value()
    return tree_sitter.Language(value)


def _fingerprint(value: tree_sitter.Language) -> tuple:
    return (
        value.name,
        value.abi_version,
        value.semantic_version,
        tuple(value.node_kind_for_id(i) for i in range(value.node_kind_count)),
        tuple(value.field_name_for_id(i) for i in range(1, value.field_count + 1)),
    )


def _conformance(schema: NodeSchema, lang: tree_sitter.Language) -> dict:
    """Compare the schema vocabulary with the loaded language ABI."""
    lang_supertypes = set()
    for i in lang.supertypes:
        kind = lang.node_kind_for_id(i)
        if kind is not None:
            lang_supertypes.add(kind)
    lang_concrete = set()
    for i in range(lang.node_kind_count):
        kind = lang.node_kind_for_id(i)
        if kind is not None and lang.node_kind_is_named(i) and \
                lang.node_kind_is_visible(i):
            lang_concrete.add(kind)
    lang_concrete -= lang_supertypes
    lang_fields = set()
    for i in range(1, lang.field_count + 1):
        field = lang.field_name_for_id(i)
        if field is not None:
            lang_fields.add(field)

    schema_concrete = {
        item.type for item in schema.node_types
        if item.named and item.subtypes is None
    }
    schema_fields = {
        field
        for item in schema.node_types
        for field in (item.fields or {})
    }
    missing = sorted(lang_concrete - schema_concrete)
    return {
        "alien_kinds": sorted(schema_concrete - lang_concrete - lang_supertypes),
        "alien_fields": sorted(schema_fields - lang_fields),
        "missing_kinds": missing,
        "missing_ratio": len(missing) / max(len(lang_concrete), 1),
    }


def _conformance_error(verdict: dict) -> str:
    def sample(values: list[str]) -> str:
        limit = 8
        shown = values[:limit]
        suffix = " ..." if len(values) > limit else ""
        return ", ".join(repr(value) for value in shown) + suffix

    return (
        "schema does not conform to loaded language: "
        f"alien kinds [{sample(verdict['alien_kinds'])}], "
        f"alien fields [{sample(verdict['alien_fields'])}], "
        f"missing kinds [{sample(verdict['missing_kinds'])}], "
        f"missing ratio {verdict['missing_ratio']:.1%}"
    )


def _verify_conformance(schema: NodeSchema, lang: tree_sitter.Language) -> None:
    verdict = _conformance(schema, lang)
    if verdict["alien_kinds"] or verdict["alien_fields"] or \
            verdict["missing_ratio"] > 0.25:
        raise SchemaDriftError(_conformance_error(verdict))


class Grammar:
    """A language, its schema, and its generated node namespace."""

    __slots__ = (
        "_bundle_path", "astgrep_is_bundle", "astgrep_name", "language",
        "metadata", "namespace", "schema",
    )

    def __init__(self, language=None, schema: NodeSchema | None = None,
                 namespace: SimpleNamespace | None = None, *,
                 metadata: dict | None = None, bundle_path=None):
        self.language = language
        self.schema = schema
        self.namespace = namespace
        self.metadata = dict(metadata or {})
        self._bundle_path = Path(bundle_path) if bundle_path is not None else None
        self.astgrep_name = (
            None if self._bundle_path is not None
            else getattr(language, "name", None))
        self.astgrep_is_bundle = False

    @property
    def nodes(self) -> SimpleNamespace | None:
        return self.namespace

    @classmethod
    def load(cls, language, schema, *, schema_name: str | None = None,
             verify: bool = True) -> Grammar:
        """Bind a schema to a language and verify their ABI vocabulary.

        Set ``verify=False`` only for tests that intentionally use a synthetic
        schema with an unrelated real language. Shipped schemas must verify.
        """
        if schema is None:
            raise TypeError("Grammar.load() requires a node schema")
        schema = load_schema(schema, name=schema_name)
        raw = _language(language)
        if raw is not None and verify:
            _verify_conformance(schema, raw)
        if raw is not None and schema_name and raw.name and \
                raw.name != schema_name:
            raise SchemaDriftError(
                f"schema {schema_name!r} does not match loaded language "
                f"{raw.name!r}; use the node-types.json from the same grammar "
                "version")
        return cls(raw, schema, build_namespace(schema, raw))

    @classmethod
    def load_bundle(cls, directory) -> Grammar:
        from .loader import load_bundle as load_artifact

        bundle = load_artifact(directory)
        if bundle.schema is None:
            raise BundleError(
                f"bundle {directory!s} has no node-schema.json; "
                "Grammar.load_bundle requires a schema-backed bundle")
        schema = cast(NodeSchema, bundle.schema)
        _verify_conformance(schema, bundle.language)
        nodes_path = bundle.path / "nodes.py"
        if nodes_path.exists():
            module_name = f"_pydantree_bundle_nodes_{id(bundle)}"
            spec = importlib.util.spec_from_file_location(module_name, nodes_path)
            if spec is None or spec.loader is None:
                raise BundleError(f"cannot import generated nodes from {nodes_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            namespace = SimpleNamespace(
                **{name: value for name, value in vars(module).items()
                   if not name.startswith("_")})
            fingerprint = tuple(getattr(module, "__fingerprint__", ()))
        else:
            namespace = build_namespace(schema, bundle.language)
            fingerprint = ()
        grammar = cls(bundle.language, schema, namespace,
                      metadata=bundle.metadata, bundle_path=bundle.path)
        if fingerprint:
            grammar.check_fingerprint(fingerprint)
        return grammar

    def register_astgrep(self, name: str | None = None, *, extensions=None,
                         meta_var_char: str | None = None,
                         expando_char: str | None = None) -> str:
        """Register this bundle grammar as an ast-grep dynamic language.

        The registration name defaults to ``astgrep_name`` metadata, then the
        grammar's export symbol. Bundle metadata supplies the export symbol,
        artifact path, and metavariable sigil. Call the module-level
        ``register_bundle_languages`` function when several bundles must be
        registered in one process because ast-grep accepts dynamic languages
        only in its first registration call.
        """
        if self._bundle_path is None:
            raise BundleError(
                "Grammar.register_astgrep() requires a Grammar loaded from a "
                "bundle; use register_bundle_language() for a standalone .so")
        export_name = self.metadata.get("name")
        if not export_name:
            raise BundleError(
                f"bundle metadata for {self._bundle_path} has no grammar "
                "export symbol in 'name'")
        symbol = self.metadata.get(
            "language_symbol", f"tree_sitter_{export_name}")
        registration_name = (
            name or self.metadata.get("astgrep_name") or export_name)
        artifact = self._bundle_path / self.metadata.get(
            "artifact", "grammar.so")
        configured_extensions = (
            extensions if extensions is not None
            else self.metadata.get("extensions"))
        configured_meta_var_char = (
            meta_var_char if meta_var_char is not None
            else self.metadata.get("meta_var_char"))
        configured_expando_char = (
            expando_char if expando_char is not None
            else self.metadata.get("expando_char"))
        from .pattern import register_bundle_language
        registered = register_bundle_language(
            registration_name, artifact, symbol,
            extensions=configured_extensions,
            meta_var_char=configured_meta_var_char,
            expando_char=configured_expando_char)
        self.astgrep_name = registered
        self.astgrep_is_bundle = True
        return registered

    def check_fingerprint(self, fingerprint: tuple) -> None:
        if self.language is not None and tuple(fingerprint) != \
                _fingerprint(self.language):
            expected_name = fingerprint[0] if fingerprint else "unknown"
            raise SchemaDriftError(
                "generated node universe for "
                f"{expected_name!r} does not match loaded grammar "
                f"{getattr(self.language, 'name', None)!r}")

    @classmethod
    def _from_generated(cls, module_name: str, language_import: str,
                        fingerprint: tuple):
        module: ModuleType | None = sys.modules.get(module_name)
        if module is None:
            return cls()
        language = _language(language_import)
        expected = tuple(fingerprint)
        if language is not None and expected and _fingerprint(language) != expected:
            raise SchemaDriftError(
                f"generated node universe for {module_name!r} does not match "
                f"loaded language {getattr(language, 'name', None)!r}")
        schema = getattr(module, "__schema__", None)
        namespace = SimpleNamespace(
            **{name: value for name, value in vars(module).items()
               if not name.startswith("_")})
        if schema is not None:
            namespace = SimpleNamespace(
                **{name: value for name, value in vars(module).items()
                   if not name.startswith("_")})
        return cls(language, schema, namespace)

    def parse(self, source: str | bytes) -> Tree:
        if self.language is None:
            raise RuntimeError("this generated Grammar has no loaded language")
        if isinstance(source, str):
            source = source.encode("utf-8")
        return Tree(self, tree_sitter.Parser(self.language).parse(source))

class Tree:
    """A parsed tree carrying its grammar for typed ``find`` operations."""

    __slots__ = ("grammar", "raw")

    def __init__(self, grammar: Grammar, raw: tree_sitter.Tree):
        self.grammar = grammar
        self.raw = raw

    @property
    def root_node(self):
        return self.raw.root_node

    def find(self, cls: type[Node]) -> list:
        return self.find_in(self.raw.root_node, cls)

    def find_one(self, cls: type[Node]):
        matches = self.find(cls)
        return matches[0] if matches else None

    def find_in(self, node, cls: type[Node]) -> list:
        raw = node._node if isinstance(node, Node) else node
        return find_in(raw, cls, self.grammar.language)
