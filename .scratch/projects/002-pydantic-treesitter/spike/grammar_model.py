"""
GrammarModel IR — a Pydantic discriminated union mirroring tree-sitter's
*real* `grammar.json` node schema (verified against tree-sitter-cli 0.25.3,
`cli/generate/src/parse_grammar.rs`).

Every node is a frozen Pydantic model with a `type` discriminator. Because the
IR is Pydantic, `model_dump_json()` on a Grammar *is* grammar.json, and
`model_validate_json()` round-trips it. Style reference: sketch.py from 017;
node set adapted to the real grammar.json schema.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class RuleNode(BaseModel):
    """Base for all rule nodes. `type` is the serde tag in grammar.json."""

    model_config = {"frozen": True}

    type: str


# --- leaf nodes ------------------------------------------------------------

class SymbolNode(RuleNode):
    type: Literal["SYMBOL"] = "SYMBOL"
    name: str


class StrNode(RuleNode):
    """STRING — a literal string in the grammar (becomes an anonymous token)."""
    type: Literal["STRING"] = "STRING"
    value: str


class PatternNode(RuleNode):
    """PATTERN — a regex token. Only `i` is a supported flag ('u'/'v' ignored,
    anything else warns). Mirrors parse_grammar.rs PATTERN handling."""
    type: Literal["PATTERN"] = "PATTERN"
    value: str
    flags: str | None = None


class BlankNode(RuleNode):
    """BLANK — the empty rule (epsilon). Used by `opt()` -> choice(x, BLANK)."""
    type: Literal["BLANK"] = "BLANK"


# --- compound nodes --------------------------------------------------------

class SeqNode(RuleNode):
    type: Literal["SEQ"] = "SEQ"
    members: list["Rule"]


class ChoiceNode(RuleNode):
    type: Literal["CHOICE"] = "CHOICE"
    members: list["Rule"]


class RepeatNode(RuleNode):
    """REPEAT — 0+ repetitions. NOTE: the CLI desugars this internally to
    choice(repeat(content), BLANK) during parsing (parse_grammar.rs)."""
    type: Literal["REPEAT"] = "REPEAT"
    content: "Rule"


class Repeat1Node(RuleNode):
    """REPEAT1 — 1+ repetitions."""
    type: Literal["REPEAT1"] = "REPEAT1"
    content: "Rule"


class FieldNode(RuleNode):
    type: Literal["FIELD"] = "FIELD"
    name: str
    content: "Rule"


class AliasNode(RuleNode):
    type: Literal["ALIAS"] = "ALIAS"
    value: str
    named: bool
    content: "Rule"


class TokenNode(RuleNode):
    """TOKEN — force the content to lex as a single token. SYMBOL inside a
    TOKEN is an error in the CLI (parse_grammar.rs `UnexpectedRule`)."""
    type: Literal["TOKEN"] = "TOKEN"
    content: "Rule"


class ImmediateTokenNode(RuleNode):
    type: Literal["IMMEDIATE_TOKEN"] = "IMMEDIATE_TOKEN"
    content: "Rule"


# --- precedence wrappers ---------------------------------------------------

# grammar.json allows an integer OR a precedence-name string
# (PrecedenceValueJSON is `#[serde(untagged)] Integer(i32) | Name(String)`);
# `int | str` on the `value` fields validates both.


class PrecNode(RuleNode):
    type: Literal["PREC"] = "PREC"
    value: int | str
    content: "Rule"


class PrecLeftNode(RuleNode):
    type: Literal["PREC_LEFT"] = "PREC_LEFT"
    value: int | str
    content: "Rule"


class PrecRightNode(RuleNode):
    type: Literal["PREC_RIGHT"] = "PREC_RIGHT"
    value: int | str
    content: "Rule"


class PrecDynamicNode(RuleNode):
    """PREC_DYNAMIC — runtime dynamic precedence; used with `conflicts` for
    intentional ambiguity. value is always an integer."""
    type: Literal["PREC_DYNAMIC"] = "PREC_DYNAMIC"
    value: int
    content: "Rule"


class ReservedNode(RuleNode):
    """RESERVED — reserved-word context (new in tree-sitter 0.25).
    `context_name` labels a set of reserved words that disable matching rules."""
    type: Literal["RESERVED"] = "RESERVED"
    context_name: str
    content: "Rule"


# The tagged union. This is what makes serialize -> deserialize reconstruct the
# correct subtype (see round-trip validation in main.py).
Rule = Annotated[
    Union[
        SymbolNode, StrNode, PatternNode, BlankNode,
        SeqNode, ChoiceNode, RepeatNode, Repeat1Node,
        FieldNode, AliasNode, TokenNode, ImmediateTokenNode,
        PrecNode, PrecLeftNode, PrecRightNode, PrecDynamicNode,
        ReservedNode,
    ],
    Field(discriminator="type"),
]

# --- grammar-level container ------------------------------------------------

class GrammarModel(BaseModel):
    """Mirror of the `GrammarJSON` struct from parse_grammar.rs.

    Fields that the CLI marks `#[serde(default)]` are optional here; `name`
    and `rules` are required. NOTE: this CLI version has NO `start` field —
    the start rule is implicit (the first rule, conventionally `source_file`).
    There IS a `reserved` map (0.25+ feature).
    """

    model_config = {"frozen": False}  # grammar is mutable (registry)

    name: str
    rules: dict[str, Rule]
    precedences: list[list[Rule]] = Field(default_factory=list)
    conflicts: list[list[str]] = Field(default_factory=list)
    externals: list[Rule] = Field(default_factory=list)
    extras: list[Rule] = Field(default_factory=list)
    inline: list[str] = Field(default_factory=list)
    supertypes: list[str] = Field(default_factory=list)
    word: str | None = None
    reserved: dict[str, list[Rule]] = Field(default_factory=dict)


# Forward refs resolve after all node classes are defined.
for _cls in (SeqNode, ChoiceNode, RepeatNode, Repeat1Node, FieldNode,
             AliasNode, TokenNode, ImmediateTokenNode, PrecNode,
             PrecLeftNode, PrecRightNode, PrecDynamicNode, ReservedNode):
    _cls.model_rebuild()
