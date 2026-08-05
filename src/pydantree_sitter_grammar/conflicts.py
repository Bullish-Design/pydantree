"""
pydantree_sitter_grammar.conflicts — conflict -> Python-source remapping.

`tree-sitter generate --json` emits a machine-readable conflict report on
STDERR (exit 1, fail-fast on the first conflict). The JSON is the serde
serialization of `GenerateError::BuildTables(ParseTableBuilderError::Conflict)`
(cli/generate/src/build_tables/build_parse_table.rs):

    ConflictError {
      symbol_sequence: Vec<String>,           # ambiguous parse path so far
      conflicting_lookahead: String,          # token that can't be decided
      possible_interpretations: [             # the competing parses
        { variable_name: String,              #   THE grammar rule (variable)
          production_step_symbols: [...],     #   the production's RHS
          step_index, done, preceding_symbols,
          precedence, associativity },
      ],
      possible_resolutions: [                 # suggested fixes
        { Precedence: {symbols}}, {Associativity: {symbols}}, {AddConflict: {symbols}},
      ],
    }

`variable_name` maps 1:1 to a grammar rule whose DSL definition site we
recorded at build time (builder.Grammar.sites), so the raised
GrammarConflictError names the author's `g.rule(...)` call lines, shows the
ambiguous input shape and the competing productions, and renders the
generator's `possible_resolutions` as suggested fixes.

Phase-0 caveats (durable): only the FIRST conflict is reported per run (the
CLI is fail-fast) — the fix loop is one-conflict-at-a-time; granularity is
per-rule (+ production shape), not per-alternative.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from .builder import Grammar


@dataclass(frozen=True)
class Conflict:
    symbol_sequence: tuple[str, ...]
    conflicting_lookahead: str
    interpretations: tuple[dict, ...]
    resolutions: tuple[dict, ...]

    @property
    def involved_rules(self) -> list[str]:
        """Rule names mentioned by the interpretations (deduped, order kept)."""
        seen = []
        for i in self.interpretations:
            name = i.get("variable_name")
            if name and name not in seen:
                seen.append(name)
        return seen

    def ambiguous_shape(self) -> str:
        return " ".join(self.symbol_sequence) + " • " + self.conflicting_lookahead


def parse_conflict_json(raw: str) -> Conflict | None:
    """Parse the CLI's --json conflict report. Returns None if the output is
    not a conflict report (e.g. some other error)."""
    try:
        data = json.loads(raw)
        conflict = data["BuildTables"]["Conflict"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return None
    return Conflict(
        symbol_sequence=tuple(conflict.get("symbol_sequence", [])),
        conflicting_lookahead=conflict.get("conflicting_lookahead", ""),
        interpretations=tuple(conflict.get("possible_interpretations", [])),
        resolutions=tuple(conflict.get("possible_resolutions", [])),
    )


class GrammarConflictError(Exception):
    """Raised when tree-sitter generate reports an unresolved GLR conflict.
    Names the offending productions with their per-production Python source
    sites — the exact `seq(...)` alternative line, not just the `rule(...)`
    call (Phase 3; Phase 2 was per-rule only)."""

    def __init__(self, grammar: Grammar, conflict: Conflict,
                 raw_report: str | None = None):
        self.grammar = grammar
        self.conflict = conflict
        self.raw_report = raw_report
        super().__init__(self._render())

    def _render(self) -> str:
        c = self.conflict
        g = self.grammar
        lines = [
            f"GLR conflict in grammar {g.name!r} — cannot generate a parser.",
            "",
            f"Ambiguous shape: {c.ambiguous_shape()}",
            "Conflicting rules (from your Python source):",
        ]
        for name in c.involved_rules:
            site = g.sites.get(name)
            if site is not None:
                lines.append(f"  - g.rule({name!r}, ...) defined at {site}")
            else:
                lines.append(f"  - rule {name!r} (no recorded source site)")
        lines.append("")
        lines.append("Competing parses (per-production source sites):")
        for i, interp in enumerate(c.interpretations, 1):
            prod = "  ".join(interp.get("production_step_symbols", []))
            prec = interp.get("precedence")
            assoc = interp.get("associativity")
            extra = ""
            if prec or assoc:
                extra = f"   [precedence={prec}, associativity={assoc}]"
            name = interp.get("variable_name")
            # per-production site: the exact seq(...) alternative, if any
            prodsite = None
            if name is not None:
                prodsite = g.matching_alternative(
                    name, tuple(interp.get("production_step_symbols", [])))
            site_txt = f"   at {prodsite}" if prodsite else ""
            lines.append(f"  {i}. {name}: {prod}{extra}{site_txt}")
        lines.append("")
        lines.append("Suggested fixes from the generator:")
        for i, res in enumerate(c.resolutions, 1):
            for kind, payload in res.items():
                symbols = ", ".join(payload.get("symbols", []))
                if kind == "Precedence":
                    lines.append(f"  {i}. raise the precedence of {symbols}")
                elif kind == "Associativity":
                    lines.append(f"  {i}. add left/right associativity to {symbols}")
                elif kind == "AddConflict":
                    lines.append(f"  {i}. whitelist as intentional ambiguity: "
                                 f"conflicts=[{symbols}]")
                else:
                    lines.append(f"  {i}. {kind}: {payload}")
        return "\n".join(lines)


def remap_from_proc(grammar: Grammar, proc: subprocess.CompletedProcess,
                    *, raw_path: str | None = None):
    """Given the CompletedProcess of `tree-sitter generate --json`, parse the
    conflict and raise GrammarConflictError. Returns (Conflict, GrammarConflictError)
    for callers that want to inspect; callers should raise the error."""
    conflict = parse_conflict_json(proc.stderr)
    if conflict is None:
        raise RuntimeError(
            "tree-sitter generate failed but no conflict report was found "
            f"(exit {proc.returncode}). stderr:\n{proc.stderr[:2000]}")
    if raw_path:
        from pathlib import Path
        Path(raw_path).write_text(proc.stderr)
    err = GrammarConflictError(grammar, conflict, raw_report=proc.stderr)
    return conflict, err
