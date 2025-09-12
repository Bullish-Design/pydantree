from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Set


LOOKUP = {
    # single-char
    "(": "left_paren",
    ")": "right_paren",
    "[": "left_bracket",
    "]": "right_bracket",
    "{": "left_brace",
    "}": "right_brace",
    "<": "less_than",
    ">": "greater_than",
    ",": "comma",
    ".": "dot",
    ":": "colon",
    ";": "semicolon",
    "+": "plus",
    "-": "minus",
    "*": "asterisk",
    "/": "slash",
    "%": "percent",
    "&": "ampersand",
    "|": "pipe",
    "^": "caret",
    "~": "tilde",
    "@": "at",
    "\\": "backslash",
    "_": "underscore",
    "=": "equals",
    # two-char
    "==": "equality",
    "!=": "not_equals",
    "<=": "less_equals",
    ">=": "greater_equals",
    "+=": "plus_equals",
    "-=": "minus_equals",
    "*=": "times_equals",
    "/=": "divide_equals",
    "%=": "mod_equals",
    "&=": "ampersand_equals",
    "|=": "pipe_equals",
    "^=": "caret_equals",
    "@=": "at_equals",
    "//": "floor_div",
    "//=": "floor_div_equals",
    "**": "power",
    "**=": "power_equals",
    "<<": "left_shift",
    "<<=": "left_shift_equals",
    ">>": "right_shift",
    ">>=": "right_shift_equals",
    "->": "arrow",
    ":=": "walrus",
    "<>": "not_equals_alt",
    # spaced keywords & starred except
    "is not": "is_not",
    "not in": "not_in",
    "except*": "except_star",
    # other aliases
    "and": "logical_and",
    "or": "logical_or",
    "not": "logical_not",
    "in": "in_operator",
    "is": "is_operator",
    "lambda": "lambda_function",
    "yield": "yield_expression",
    "await": "await_expression",
    "return": "return_statement",
    "break": "break_statement",
    "continue": "continue_statement",
    "pass": "pass_statement",
    "del": "delete_statement",
    "global": "global_statement",
    "nonlocal": "nonlocal_statement",
    "assert": "assert_statement",
    "raise": "raise_statement",
    "try": "try_statement",
    "except": "except_clause",
    "finally": "finally_clause",
    "with": "with_statement",
    "class": "class_definition",
    "def": "function_definition",
    "if": "if_statement",
    "elif": "elif_statement",
    "else": "else_statement",
    "for": "for_statement",
    "while": "while_statement",
    "import": "import_statement",
    "from": "from_statement",
    "as": "as_keyword",
    "async": "async_keyword",
    "match": "match_statement",
    "case": "case_clause",
    "type": "type_alias",
    "true": "true_literal",
    "false": "false_literal",
    "none": "none_literal",
}


class NodeNameResolver:
    """
    Resolve Tree-sitter node-type strings → legal, unique Python identifiers.
    Supply *lookup* (dict) with operator / punctuation aliases, e.g. {"!=": "not_equals"}.
    """

    def __init__(self, lookup: Dict[str, str], default_prefix: str = "node") -> None:
        self.lookup = lookup
        self.seen: Set[str] = set()
        self.default_prefix = default_prefix

    # ------------------------------------------------------------------ #
    # Call the instance like a function
    # ------------------------------------------------------------------ #
    def __call__(self, raw_name: str) -> str:
        """Return a legal identifier for *raw*, ensuring global uniqueness."""

        # 1️⃣ fast, explicit match-case for known punctuation forms
        match raw_name:
            case key if key in self.lookup:
                ident = self.lookup[key]  # direct hit
            ## space-separated combos need literal patterns:
            # case "is not":
            #    ident = self.lookup["is not"]
            # case "not in":
            #    ident = self.lookup["not in"]
            # case "except*":
            #    ident = self.lookup["except*"]
            # fallback – anything not in lookup
            case _:
                ident = raw_name  # self._generic_cleanup(raw)

        # 2️⃣ uniqueness pass
        # ident = self._dedup(ident)
        ident = _snake_to_camel(ident)  # convert snake_case to CamelCase
        return ident


def _snake_to_camel(name: str) -> str:
    if name == "_":
        return "Underscore"
    if name == "except*":
        return "ExceptStar"
    class_name = "".join(part.capitalize() for part in name.split("_"))
    class_name = f"{class_name}Node"
    return class_name


def generate_from_node_types(json_path: str, out_path: str) -> None:
    """Generate strongly‑typed subclasses from a `node-types.json` spec."""

    specs: List[Dict[str, Any]] = json.loads(Path(json_path).read_text())
    lines: List[str] = [
        "from __future__ import annotations",
        "from pydantree.core import TSNode",
        "",
        "NODE_MAP: dict[str, type[TSNode]] = {}",
        "",
    ]

    for spec in specs:
        type_name: str = spec["type"]
        # class_name = _snake_to_camel(type_name)
        name_resolver = NodeNameResolver(lookup=LOOKUP)
        class_name = name_resolver(raw_name=type_name)
        fields = spec.get("fields", {})
        match_args = ["type_name", *fields.keys()]

        lines.append(f"class {class_name}(TSNode):")
        if fields:
            lines.append(f"    __match_args__ = {tuple(match_args)}")
        lines.append("    pass\n")
        lines.append(f"NODE_MAP[{type_name!r}] = {class_name}\n")

    # auto‑register when imported
    lines.append("TSNode.register_subclasses(NODE_MAP)")

    Path(out_path).write_text("\n".join(lines))
