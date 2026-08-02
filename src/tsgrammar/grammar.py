"""
tsgrammar.grammar — the canonical IR mirroring tree-sitter's real
`grammar.json` schema.

Verified against tree-sitter-cli 0.25.3 (`cli/generate/src/parse_grammar.rs`).
Every rule node is a frozen Pydantic model in a discriminated union keyed on
`type`; a `Grammar` is the top-level container. Because both sides are
Pydantic, `Grammar.model_dump_json()` *is* `grammar.json` and
`Grammar.model_validate_json()` round-trips it — which is what makes importing
existing community grammars and re-emitting them free.

Schema facts pinned to 0.25.3 (see `cli/generate/src/parse_grammar.rs`):

- `RuleJSON` variants (the node table below).
- `PrecedenceValueJSON` is untagged `Integer(i32) | Name(String)` — so
  `PREC`/`PREC_LEFT`/`PREC_RIGHT` take `value: int | str`. Named and integer
  precedence do NOT compare against each other at conflict time.
- `GrammarJSON`: `name` (required), `rules` (required, **ordered — the FIRST
  rule is the start rule; there is no `start` field**), `precedences`
  (`Vec<Vec<Rule>>`, only STRING/SYMBOL entries allowed), `conflicts`
  (`Vec<Vec<String>>`), `externals` (`Vec<Rule>`), `extras` (`Vec<Rule>`),
  `inline` (`Vec<String>`), `supertypes` (`Vec<String>`), `word`
  (`Option<String>`), `reserved` (`Map<String, Vec<Rule>>` — the value must
  be an array of rules, else `InvalidReservedWordSet`).
- There is no `OPTIONAL` node — `opt(x)` is sugar for `CHOICE(x, BLANK)`.
- `PATTERN.flags` is `Option<String>`; only `i` is honored by the generator.
- `REPEAT` is internally desugared to `choice(repeat(content), BLANK)`, so
  nullable content inside `REPEAT` is a *semantic* hazard, not a CLI error.
- Unused rules are **silently pruned** by the CLI (see `variable_is_used`):
  anything not reachable from the first rule, not referenced by `extras`/
  `externals`, and not the `word` rule is dropped — along with its entries in
  `conflicts`/`inline`/`supertypes`/`precedences`. The analyzer's unused-rule
  check exists to catch this before the CLI does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator
class RuleNode(BaseModel):
    """Base for all rule nodes. `type` is the serde tag in grammar.json."""

    model_config = {"frozen": True}

    type: str


# --- leaf nodes ------------------------------------------------------------

class SymbolNode(RuleNode):
    """SYMBOL — a reference to a named rule (recursion in the DAG-of-references)."""
    type: Literal["SYMBOL"] = "SYMBOL"
    name: str


class StrNode(RuleNode):
    """STRING — a literal string (becomes an anonymous token)."""
    type: Literal["STRING"] = "STRING"
    value: str


class PatternNode(RuleNode):
    """PATTERN — a regex token. Only `i` is a supported flag; the CLI silently
    ignores `u`/`v` and warns on anything else. Mirror parse_grammar.rs."""
    type: Literal["PATTERN"] = "PATTERN"
    value: str
    flags: str | None = None


class BlankNode(RuleNode):
    """BLANK — the empty rule (epsilon). Used by `opt()` -> choice(x, BLANK)."""
    type: Literal["BLANK"] = "BLANK"


# --- compound nodes --------------------------------------------------------

class SeqNode(RuleNode):
    type: Literal["SEQ"] = "SEQ"
    members: list[Rule]


class ChoiceNode(RuleNode):
    type: Literal["CHOICE"] = "CHOICE"
    members: list[Rule]


class RepeatNode(RuleNode):
    """REPEAT — 0+ repetitions. NOTE: the CLI desugars this internally to
    choice(repeat(content), BLANK) during parsing (parse_grammar.rs)."""
    type: Literal["REPEAT"] = "REPEAT"
    content: Rule


class Repeat1Node(RuleNode):
    """REPEAT1 — 1+ repetitions."""
    type: Literal["REPEAT1"] = "REPEAT1"
    content: Rule


class FieldNode(RuleNode):
    type: Literal["FIELD"] = "FIELD"
    name: str
    content: Rule


class AliasNode(RuleNode):
    type: Literal["ALIAS"] = "ALIAS"
    value: str
    named: bool
    content: Rule


class TokenNode(RuleNode):
    """TOKEN — force the content to lex as a single token. SYMBOL inside a
    TOKEN is an error in the CLI (parse_grammar.rs `UnexpectedRule`)."""
    type: Literal["TOKEN"] = "TOKEN"
    content: Rule


class ImmediateTokenNode(RuleNode):
    r"""IMMEDIATE_TOKEN — like TOKEN but only matches with no preceding
    whitespace (no implicit `\s*` boundary). CLI quirk: propagates the current
    `is_token` flag rather than forcing true, so a bare SYMBOL at the top level
    of an IMMEDIATE_TOKEN is tolerated by the CLI."""
    type: Literal["IMMEDIATE_TOKEN"] = "IMMEDIATE_TOKEN"
    content: Rule


# --- precedence wrappers ---------------------------------------------------

class PrecNode(RuleNode):
    """PREC — `value` is an integer OR a precedence-name string
    (`PrecedenceValueJSON` is `#[serde(untagged)] Integer(i32) | Name(String)`).
    Named vs integer precedence do not compare against each other."""
    type: Literal["PREC"] = "PREC"
    value: int | str
    content: Rule


class PrecLeftNode(RuleNode):
    type: Literal["PREC_LEFT"] = "PREC_LEFT"
    value: int | str
    content: Rule


class PrecRightNode(RuleNode):
    type: Literal["PREC_RIGHT"] = "PREC_RIGHT"
    value: int | str
    content: Rule


class PrecDynamicNode(RuleNode):
    """PREC_DYNAMIC — runtime dynamic precedence (used with `conflicts` for
    intentional ambiguity). value is always an integer."""
    type: Literal["PREC_DYNAMIC"] = "PREC_DYNAMIC"
    value: int
    content: Rule


class ReservedNode(RuleNode):
    """RESERVED — a reserved word in a named context (tree-sitter 0.25+).
    When the context is active, the content is *disabled* from matching,
    letting the word lex as an identifier instead. `context_name` labels the
    context (must be declared in the grammar-level `reserved` map)."""
    type: Literal["RESERVED"] = "RESERVED"
    context_name: str
    content: Rule


# The tagged union — the load-bearing structure. Serialize/deserialize
# reconstructs the correct subtype via the `type` discriminator.
Rule = Annotated[
    SymbolNode | StrNode | PatternNode | BlankNode | SeqNode | ChoiceNode | RepeatNode | Repeat1Node | FieldNode | AliasNode | TokenNode | ImmediateTokenNode | PrecNode | PrecLeftNode | PrecRightNode | PrecDynamicNode | ReservedNode,
    Field(discriminator="type"),
]


# --- grammar-level container ------------------------------------------------

class Grammar(BaseModel):
    """Mirror of `GrammarJSON` from parse_grammar.rs.

    - `rules` is an **ordered** dict; the FIRST rule is the start rule. There
      is no `start` field in 0.25.3.
    - `name` and `rules` are required; everything else defaults.
    - `precedences` entries may contain only STRING (precedence *names*) and
      SYMBOL rules (the CLI errors with `Unexpected` otherwise).
    - `reserved` maps a context name to a list of rule nodes.
    """

    model_config = {"extra": "forbid"}

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

    @model_validator(mode="before")
    @classmethod
    def _drop_schema_key(cls, data):
        """Published grammar.json files (e.g. tree-sitter-bash) carry a
        `$schema` pointer; it is not part of the schema and must not break
        import. Everything else stays strict (`extra=forbid`)."""
        if isinstance(data, dict):
            data.pop("$schema", None)
        return data

    @property
    def start_rule(self) -> str:
        """The start rule — the FIRST entry of `rules` (there is no `start`
        field in 0.25.3; the CLI makes rule index 0 the start symbol)."""
        if not self.rules:
            raise ValueError("grammar has no rules — cannot determine start rule")
        return next(iter(self.rules))

    # -- emission -----------------------------------------------------------
    def emit_json(self, path) -> None:
        """Serialize this grammar as grammar.json (exclude None/empty for the
        clean canonical form the CLI expects)."""
        import json
        from pathlib import Path

        path = Path(path)
        path.write_text(self.model_dump_json(indent=2, exclude_none=True))
        json.loads(path.read_text())  # sanity: must parse as JSON

    def emit_bundle(self, dirpath) -> Path:
        """Emit grammar.json + the minimal ABI-15 tree-sitter.json config into
        `dirpath`. Returns the grammar.json path. (ABI 15 matches the Python
        bindings 0.26.0; without the config the CLI falls back to ABI 14.)"""
        from pathlib import Path

        dirpath = Path(dirpath)
        dirpath.mkdir(parents=True, exist_ok=True)
        cfg = dirpath / "tree-sitter.json"
        if not cfg.exists():
            cfg.write_text('{"metadata": {"version": "0.1.0"}}\n')
        json_path = dirpath / "grammar.json"
        self.emit_json(json_path)
        return json_path


# Forward refs resolve after all node classes are defined.
for _cls in (
    SeqNode, ChoiceNode, RepeatNode, Repeat1Node, FieldNode,
    AliasNode, TokenNode, ImmediateTokenNode, PrecNode,
    PrecLeftNode, PrecRightNode, PrecDynamicNode, ReservedNode,
):
    _cls.model_rebuild()
