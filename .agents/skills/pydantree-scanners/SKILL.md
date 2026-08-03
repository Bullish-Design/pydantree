---
name: pydantree-scanners
description: The pydantree external-scanner library — the airtight mechanism (externals in scanner order, scanner= to the build, content-addressed cache, ExternalScannerRequiredError), the two gotchas (mid-whitespace scans; multiple externals valid in one state), the five seeds, and the step-by-step recipe for adding a per-language scanner copy. Use when wiring a scanner into a grammar build or adding a new scanner to the library.
---

# pydantree — the external-scanner library

External scanners are the ONE place "you only write the grammar" is false:
indentation, heredocs, and matched delimiters need a C scanner. Full
contract: `../../docs/scanner-library.md`.

## The mechanism (the contract)

1. Declare externals in the scanner's `enum TokenType` order:
   ```python
   g.external(tg.tok("HEREDOC_START"), tg.tok("HEREDOC_BODY"))
   ```
2. Pass the scanner to the build:
   ```python
   result = tg.build_builder(g, scanner=tg.bash_heredoc_scanner_path())
   ```
3. Externals without a scanner -> `ExternalScannerRequiredError` (BEFORE
   gcc's link failure — the escape hatch is airtight).
4. The cache key content-addresses scanner.c — a scanner edit invalidates
   the cache (use a fresh `cache_dir=` when iterating to avoid stale-cache
   confusion).
5. The `.c` ships as package data in the heavy wheel; `tg.scanner_for(name)`
   maps grammar names to the canonical scanner.

## The five seeds

- `indent_scanner.c` (pymini) — the canonical indentation model.
- `heredoc_scanner.c` (hmini) — `<<TAG` + content; BODY INCLUDES the
  delimiter line.
- `matched_delimiter_scanner.c` (dmini) — one `(...)` group, strict at EOF.
- `py_indent_scanner.c` (pyindent) — REAL Python logical-line semantics
  (adapted from tree-sitter-python).
- `bash_heredoc_scanner.c` (bashmini) — the MULTI-heredoc pending queue,
  `<<-` indent-stripped, quoted delimiters (adapted from tree-sitter-bash).

Each seed has a mini-grammar in `../../.scratch/` + corpus + parse-error tests in
`tests/test_scanners.py`.

## The two gotchas (design for them)

1. **The lexer calls the scanner MID-WHITESPACE.** The lookahead may be the
   space before your token. Skip whitespace FIRST, and do NOT gate the
   dispatch on the raw lookahead character — let the token handler skip and
   check. (bashmini bug #1: `if (valid && lookahead == '<')` never fired.)
2. **Multiple externals can be valid in ONE parser state.** The source
   disambiguates — a `<` is always a heredoc START. When START declines,
   the dispatch must FALL THROUGH to BODY, not return false. (bashmini bug
   #2: bodies were lexed as identifiers.)

## The canonical cadences

- **Indentation**: `mark_end` BEFORE the loop; the newline is SKIPPED (the
  emitted NEWLINE is zero-width), so the next scan re-crosses it and can
  measure indentation for INDENT/DEDENT — the two-call cadence. Blocks are
  `INDENT statements DEDENT`. Comment lines count as newlines; EOF flushes
  pending DEDENTs.
- **Heredoc**: capture the delimiter in scanner state (serialize it);
  BODY reads lines and ends AT the delimiter line (token includes it, the
  trailing newline is a grammar token). The bash copy adds the pending
  queue (served in opening order), `<<-` (tabs allowed on the delimiter
  line), quoted delimiters. EOF is lenient.
- **Matched delimiter**: count depth; refuse unbalanced at EOF (strict).

## Recipe: add a per-language scanner copy

1. Read the upstream scanner (`tree-sitter-<lang>/src/scanner.c`), adapt
   the mechanism — do NOT copy wholesale; document the honest scope line in
   the file header (the mechanism is reusable; string/expansion subtleties
   are usually out of scope).
2. Write `src/tsgrammar/scanners/<name>_scanner.c`: enum matching the
   externals order; the five `tree_sitter_<grammar>_external_scanner_*`
   entry points; serialize/deserialize ONLY the needed state, within
   `TREE_SITTER_SERIALIZATION_BUFFER_SIZE`; handle BOTH gotchas.
3. Mini-grammar in `../../.scratch/` (GOOD/GOOD_EXPECTED + semantic cases;
   `tg.render` confirms expectations — it shows anonymous tokens AND
   extras).
4. Tests in `tests/test_scanners.py`: corpus cases + a parse-error case +
   a `scanner_for` registration check.
5. Register: `*_scanner_path()` + `_CANONICAL` entry in
   `src/tsgrammar/scanners/__init__.py`; re-export from
   `tsgrammar/__init__.py` (`__all__` too).
6. **Nothing to reinstall** — the dev venv resolves `src/` directly (the
   `_pydantree_src.pth`), so the new scanner is immediately importable.
7. Verify the wheel: `tests/test_packaging.py` asserts the `.c` rides the
   heavy wheel.

## What NOT to do

- Do NOT copy the TSLexer struct to peek — `advance` casts to the enclosing
  `Lexer*`; a stack copy corrupts state. Buffer the line and compare, or
  split the token into BODY/END like upstream bash.
- Do NOT gate the dispatch on the raw lookahead (§gotcha 1).
- Do NOT return a START decline without falling through to BODY (§gotcha 2).
- Do NOT skip a leading newline in a body scanner unless your grammar (like
  hmini's) has that newline as a regular token — a blank first line is
  body content.
