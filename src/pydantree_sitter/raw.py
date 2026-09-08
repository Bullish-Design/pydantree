"""The isolated ``__raw_query__`` escape hatch."""

from __future__ import annotations

import tree_sitter

from .errors import QueryBuildError, SchemaCheckError

__all__ = ["Cursor", "MatchView", "Query", "RawQuery"]


class RawQuery(str):
    """A literal tree-sitter query assigned to ``Node.__raw_query__``."""

    __slots__ = ()


class Query:
    """A literal tree-sitter query compiled for one language."""

    def __init__(self, source: str):
        self.source = str(source)
        self._compiled: tree_sitter.Query | None = None

    @classmethod
    def raw(cls, source: str) -> Query:
        return cls(source)

    def compile(self, language: tree_sitter.Language) -> tree_sitter.Query:
        if self._compiled is not None:
            return self._compiled
        if not isinstance(language, tree_sitter.Language):
            language = tree_sitter.Language(language)
        try:
            self._compiled = tree_sitter.Query(language, self.source)
        except tree_sitter.QueryError as error:
            raise QueryBuildError(
                f"raw .scm rejected by Query(): {error}\n---\n{self.source}") \
                from error
        return self._compiled

    def capture_names(self, language: tree_sitter.Language) -> set[str]:
        query = self.compile(language)
        return {query.capture_name(index)
                for index in range(query.capture_count)}

    def check_captures(self, language: tree_sitter.Language,
                       fields: set[str], *,
                       compiled: tree_sitter.Query | None = None) -> None:
        query = compiled if compiled is not None else self.compile(language)
        names = {query.capture_name(index)
                 for index in range(query.capture_count)}
        unknown = names - fields
        if unknown:
            raise SchemaCheckError(
                f"__raw_query__ captures {sorted(unknown)} that no field "
                f"declares — model fields: {sorted(fields)}")


class Cursor:
    """Iterate matches for a compiled raw query."""

    def __init__(self, query: tree_sitter.Query, tree: tree_sitter.Tree):
        self.query = query
        self.tree = tree

    def matches(self) -> list[MatchView]:
        return [MatchView(index, captures)
                for index, captures in
                tree_sitter.QueryCursor(self.query).matches(
                    self.tree.root_node)]

    def matches_on(self, node: tree_sitter.Node) -> list[MatchView]:
        return [MatchView(index, captures)
                for index, captures in tree_sitter.QueryCursor(
                    self.query).matches(node)]


class MatchView:
    """One raw-query match with tree-sitter node captures."""

    def __init__(self, pattern_index: int, captures: dict[str, list]):
        self.pattern_index = pattern_index
        self._captures = captures

    @property
    def caps(self) -> dict[str, list]:
        return self._captures

    def nodes(self, name: str) -> list:
        return list(self._captures.get(name, []))

    def text(self, name: str) -> str | None:
        nodes = self._captures.get(name)
        if not nodes:
            return None
        return (nodes[0].text or b"").decode("utf-8")
