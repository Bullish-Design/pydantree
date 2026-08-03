# pydantree — the external-scanner library

External scanners are the ONE place "you only write the grammar" is
explicitly false (CONCEPT §4.6): indentation-sensitive languages, heredocs,
matched delimiters, and some string forms need a C scanner. This document is
the working contract — for authors who just want to USE a scanner, and for
developers adding a per-language scanner copy to the library.

---

## 1. The airtight mechanism (the contract)

1. **Declare the externals in the scanner's expected order** (the scanner's
   `enum TokenType` order must match the `g.external(...)` order — the
   generated parser maps external index → symbol):

   ```python
   g.external(tg.tok("NEWLINE"), tg.tok("INDENT"), tg.tok("DEDENT"))
   ```

2. **Pass the scanner path to the build:**

   ```python
   result = tg.build_builder(g, scanner=tg.py_indent_scanner_path())
   ```

   A grammar that declares externals but gets NO scanner raises
   `ExternalScannerRequiredError` — naming the externals — BEFORE gcc's link
   failure (the escape hatch is airtight).

3. **The cache key content-addresses the scanner.c** (`sha256(scanner.c)` is
   folded into the pipeline cache key), so a scanner build and a
   scanner-less build never collide — and a scanner edit invalidates the
   cache.

4. **The scanner ships as package data in the heavy wheel**
   (`pydantree-tsgrammar`), reachable via the library table:

   ```python
   tg.scanner_for("pyindent")    # -> Path to py_indent_scanner.c (or None)
   ```

## 2. The five seeds

| scanner | externals | grammar | mechanism |
|---|---|---|---|
| `indent_scanner.c` | NEWLINE, INDENT, DEDENT | pymini | the canonical indentation model (Phase 5 seed) |
| `heredoc_scanner.c` | HEREDOC_START, HEREDOC_BODY | hmini | `<<TAG` + content, the BODY token INCLUDES the delimiter line |
| `matched_delimiter_scanner.c` | BALANCED | dmini | one `(...)` group of arbitrary nesting, strict at EOF |
| `py_indent_scanner.c` | NEWLINE, INDENT, DEDENT | pyindent | REAL Python logical-line semantics (adapted from tree-sitter-python) |
| `bash_heredoc_scanner.c` | HEREDOC_START, HEREDOC_BODY | bashmini | the MULTI-heredoc pending queue, `<<-` indent-stripped, quoted delimiters (adapted from tree-sitter-bash) |

Each seed lives with a mini-grammar in `../.scratch/` (pymini, hmini, dmini,
pyindent, bashmini) — a tiny language that exercises exactly the scanner's
semantics — plus corpus tests and a parse-error test in
`tests/test_scanners.py`.

## 3. The two gotchas (verified facts — design for them)

1. **The lexer calls the scanner MID-WHITESPACE.** After an identifier, the
   lookahead may be the space before the token the scanner should produce.
   The scanner must skip leading whitespace itself — and the DISPATCH must
   not gate on the raw lookahead character. (The bashmini scanner's first
   bug: `if (valid_symbols[START] && lexer->lookahead == '<')` never fired
   because the lookahead was the space.)
2. **Multiple externals can be valid in ONE parser state.** The source must
   disambiguate. The canonical example: at a heredoc body position, both
   HEREDOC_START and HEREDOC_BODY are valid — a `<` is always a START, and
   when START declines the dispatch must FALL THROUGH to BODY, not return
   false. (The bashmini scanner's second bug: returning the START decline
   straight out, so bodies were lexed as identifiers.)

## 4. The canonical cadences (from the seeds — reuse these shapes)

**Indentation (the two-call cadence).** `mark_end` at the START (the emitted
NEWLINE is ZERO-WIDTH; the newline is SKIPPED, never advanced), so the next
scan re-crosses the same newline and can measure the indentation for
DEDENT/INDENT. A header's NEWLINE and its block's INDENT come from two scans
at the same position — the grammar shape is `INDENT statements DEDENT`
(NEWLINE ends statements; a NEWLINE-then-INDENT sequence cannot work because
emitting NEWLINE would consume the indentation the INDENT needs). Comment
lines count as newlines; EOF flushes pending DEDENTs.

**Heredoc.** HEREDOC_START scans `<<` (+ flags) and captures the delimiter
into the scanner state (serialized); HEREDOC_BODY reads content lines and
ends the token at the delimiter line (the token INCLUDES the delimiter line,
bash-like; the trailing newline is a regular grammar token). The bash copy
adds the pending-delimiter QUEUE (several heredocs on one command line,
served in opening order), `<<-` (leading tabs allowed on the delimiter line),
and quoted delimiters. EOF without a delimiter ends the token at EOF
(lenient, like the indentation seed).

**Matched delimiter.** Count nesting depth; refuse an unbalanced group at
EOF (strict, not silently swallowed).

## 5. Recipe: add a per-language scanner copy

1. **Read the upstream scanner first** (`tree-sitter-<lang>/src/scanner.c`).
   Adapt the canonical mechanism — do NOT copy wholesale. Decide the honest
   scope line: the MECHANISM is what's reusable (e.g. the indentation
   cadence, the heredoc queue); string/expansion subtleties are usually
   out of scope and should be documented as such in the file header.
2. **Write the scanner** at `src/tsgrammar/scanners/<name>_scanner.c`:
   - `enum TokenType` matching the `g.external(...)` order;
   - the five entry points named `tree_sitter_<grammar>_external_scanner_
     {create,destroy,serialize,deserialize,scan}`;
   - `create` allocates the state; `serialize`/`deserialize` round-trip
     ONLY the state the parser needs (the indentation stack, the heredoc
     queue) within `TREE_SITTER_SERIALIZATION_BUFFER_SIZE`;
   - handle BOTH gotchas (§3) in `scan()`.
3. **Write the mini-grammar** at `../.scratch/009-phase7/<name>.py` (or the
   next phase dir): a tiny language exercising exactly the scanner's
   semantics, with `GOOD`/`GOOD_EXPECTED` + semantic-case constants. The
   expected sexps are hand-computed from the grammar's intent (run
   `tg.render(tree.root_node)` to confirm — the renderers show anonymous
   tokens AND extras like comments).
4. **Add tests** to `tests/test_scanners.py`: corpus cases (via the `Corpus`
   harness) + a parse-error case (what the scanner REFUSES) + a
   `scanner_for` registration check.
5. **Register**: add a `*_scanner_path()` helper + a `_CANONICAL` entry in
   `src/tsgrammar/scanners/__init__.py`, re-export from
   `tsgrammar/__init__.py` (`__all__` too).
6. **Nothing to reinstall** — the dev venv resolves `src/` directly (the
   `_pydantree_src.pth`), so new scanner files are immediately importable.
7. **Verify the wheel**: `tests/test_packaging.py` builds the heavy wheel
   and asserts the scanner `.c` rides as package data.

## 6. What NOT to do (learned the hard way)

- **Do not copy the TSLexer struct to peek.** `lexer->advance` casts the
  TSLexer to the enclosing `Lexer*` (`container_of` style) — a stack copy
  corrupts the position state. If your design needs to look ahead a line,
  buffer the line and compare (the hmini/bashmini approach), or split the
  token (upstream bash's BODY/END pair) — don't peek.
- **Do not gate the dispatch on the raw lookahead** (§3.1).
- **Do not `return scan_start(...)` when BODY is also valid** (§3.2).
- **Do not skip a leading newline blindly in a body scanner** — a blank
  first line is body CONTENT (unless your grammar, like hmini's, has the
  newline before the body as a regular token).
- **Do not forget the serialize/deserialize contract** — the parser calls
  `deserialize` before every scan; a scanner whose state grows without bound
  breaks incremental parsing.

## 7. The honest scope line

The library's value is the MECHANISM being reusable, not a full replication
of every upstream scanner's state machine. The real Python scanner's string
handling and the bash scanner's body interpolation are documented as out of
scope in the file headers — landing the canonical cadence + the source's
disambiguation is the per-language copy. When a new language's scanner would
balloon, land the assessment (what it would take, who it serves) and move
on.
