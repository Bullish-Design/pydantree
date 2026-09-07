"""Does a `ruff format` pass rescue the §15 round-trip invariant?

The invariant: a replacement whose template EQUALS the pattern must return
`new_source == source`, for every corpus file. IMPLEMENTATION.md §1.3 records
that it fails, because an ast-grep template puts a literal space where the
source had a line break.

The proposal under test: compare FORMATTED forms instead of raw text.

    format(replace_all(src, same_template)) == format(src)

Three measurements, because they answer different questions:

  A. is the corpus already `ruff format`-clean? If not, `format(src) != src`
     and the invariant has silently changed meaning.
  B. raw round trip — the current, failing baseline.
  C. formatted round trip — the proposal.

Run: devenv shell -- python .scratch/projects/022-astgrep-pattern/probe_format_roundtrip.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import tree_sitter_python

from pydantree_sitter import Language, Pattern
from pydantree_sitter.errors import PatternRewriteError

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parents[2]
CORPUS = sorted((ROOT / "src" / "pydantree_sitter").glob("*.py"))

# The same identity templates, one per shape. Each is its own pattern AND its
# own replacement, which is what "round trip" means here.
TEMPLATES = [
    "def $NAME($$$ARGS): $$$BODY",
    "if $COND: $$$BODY",
    "for $VAR in $ITER: $$$BODY",
    "class $NAME($$$BASES): $$$BODY",
    "$A = $B",
    "return $VAL",
]


def ruff_format(text: str) -> str | None:
    """`text` formatted, or None if ruff refused it."""
    proc = subprocess.run(
        ["ruff", "format", "--stdin-filename", "probe.py", "-"],
        input=text, capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def main() -> int:
    already_clean = 0
    unformattable = 0
    raw_ok = raw_total = 0
    fmt_ok = fmt_total = 0
    fmt_failures: list[str] = []
    refused = 0
    lang = Language.from_module(tree_sitter_python)
    patterns = [(t, Pattern(t, language=lang)) for t in TEMPLATES]

    for path in CORPUS:
        src = path.read_text(encoding="utf-8")
        formatted_src = ruff_format(src)
        if formatted_src is None:
            unformattable += 1
            continue
        if formatted_src == src:
            already_clean += 1

        for template, pat in patterns:
            try:
                result = pat.replace_all(src, template)
            except PatternRewriteError:
                # nested matches — the module refuses by design (§8). Not a
                # round-trip question.
                refused += 1
                continue
            if result.count == 0:
                continue

            raw_total += 1
            raw_ok += result.new_source == src

            formatted_new = ruff_format(result.new_source)
            fmt_total += 1
            if formatted_new is not None and formatted_new == formatted_src:
                fmt_ok += 1
            else:
                fmt_failures.append(f"{path.name} :: {template}")

    report = {
        "corpus_files": len(CORPUS),
        "already_ruff_format_clean": already_clean,
        "ruff_refused": unformattable,
        "cases_refused_for_overlap": refused,
        "raw_round_trip": {
            "cases": raw_total, "identical": raw_ok,
            "rate": round(raw_ok / raw_total, 4) if raw_total else None,
        },
        "formatted_round_trip": {
            "cases": fmt_total, "identical": fmt_ok,
            "rate": round(fmt_ok / fmt_total, 4) if fmt_total else None,
        },
        "formatted_failures": fmt_failures[:20],
    }
    (HERE / "evidence" / "format_roundtrip.json").write_text(
        json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
