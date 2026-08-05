/* pydantree_sitter_grammar scanner library — the real-Python indentation scanner (Phase 7,
 * adapted from tree-sitter-python's src/scanner.c — the canonical NEWLINE/
 * INDENT/DEDENT mechanism with REAL Python logical-line semantics, not the
 * simplified pymini seed's).
 *
 * What is adapted from upstream (the parts that make Python indentation
 * genuinely different from the pymini seed):
 *
 *   - NEWLINE only at the end of a REAL logical line: comment-only lines are
 *     skipped (they emit no NEWLINE), blank lines are skipped, and a
 *     backslash continuation (`\` + newline) keeps the logical line open.
 *   - a trailing comment after an expression (`x = 1 # note`) is NOT a line
 *     ending — the scanner declines and the grammar's comment extra handles
 *     it; the NEWLINE comes from the following newline.
 *   - `\r`/`\f` reset the indent column; `\t` counts as 8 columns.
 *   - the DEDENT is delayed past comments whose indent matches the current
 *     block (first_comment_indent_length guard — upstream's comment-aware
 *     dedent).
 *   - the two-call cadence: NEWLINE is zero-width (mark_end before the loop,
 *     the newline SKIPPED), so a header line's `NEWLINE` and the block's
 *     `INDENT` come from two scans at the same position — the canonical
 *     indentation cadence (Phase-5 appendix fact 5).
 *
 * NOT adapted (the honest scope line): the string/format/backtick handling
 * (STRING_START/.../ESCAPE_INTERPOLATION) and the bracket tracking — this
 * scanner is the indentation mechanism, the part the library is for. The
 * grammar (pyindent, .scratch/projects/009-phase7/pyindent.py) is the real header
 * shape: `if x: NEWLINE INDENT stmt* DEDENT`.
 *
 * Grammar shape (pyindent):
 *
 *   g.external(tg.tok("NEWLINE"), tg.tok("INDENT"), tg.tok("DEDENT"))
 *   g.extra(tg.ref("comment"))
 *   g.rule("if_stmt", tg.seq("if", cond, ":", NEWLINE,
 *                            INDENT, repeat(statement), DEDENT))
 */

#include "tree_sitter/parser.h"
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

enum TokenType { NEWLINE, INDENT, DEDENT };

typedef struct {
  uint16_t *columns;
  uint32_t count;
  uint32_t capacity;
} IndentStack;

static void stack_push(IndentStack *s, uint16_t c) {
  if (s->count == s->capacity) {
    s->capacity = s->capacity ? s->capacity * 2 : 8;
    s->columns = realloc(s->columns, s->capacity * sizeof(uint16_t));
  }
  s->columns[s->count++] = c;
}
static uint16_t stack_top(const IndentStack *s) { return s->columns[s->count - 1]; }
static uint16_t stack_pop(IndentStack *s) { return s->columns[--s->count]; }

void *tree_sitter_pyindent_external_scanner_create(void) {
  IndentStack *s = calloc(1, sizeof(IndentStack));
  s->count = 1;
  s->columns = malloc(sizeof(uint16_t));
  s->columns[0] = 0;
  return s;
}
void tree_sitter_pyindent_external_scanner_destroy(void *p) {
  IndentStack *s = (IndentStack *)p;
  free(s->columns);
  free(s);
}
unsigned tree_sitter_pyindent_external_scanner_serialize(void *p, char *b) {
  IndentStack *s = (IndentStack *)p;
  uint32_t sz = s->count * sizeof(uint16_t);
  if (sz > TREE_SITTER_SERIALIZATION_BUFFER_SIZE) {
    sz = TREE_SITTER_SERIALIZATION_BUFFER_SIZE;
  }
  memcpy(b, s->columns, sz);
  return sz;
}
void tree_sitter_pyindent_external_scanner_deserialize(void *p, const char *b,
                                                       unsigned n) {
  IndentStack *s = (IndentStack *)p;
  if (n > 0) {
    s->count = n / sizeof(uint16_t);
    if (s->count == 0) s->count = 1;  /* the base column is always there */
    memcpy(s->columns, b, n);
  }
}

static void skip(TSLexer *l) { l->advance(l, true); }

bool tree_sitter_pyindent_external_scanner_scan(void *payload, TSLexer *lexer,
                                                const bool *valid_symbols) {
  IndentStack *stack = (IndentStack *)payload;
  bool want = valid_symbols[NEWLINE] || valid_symbols[INDENT] ||
              valid_symbols[DEDENT];
  if (!want) return false;

  /* the canonical cadence: the emitted token is zero-width (mark_end at the
   * START), so the next scan re-crosses the same newline and can measure the
   * indentation for DEDENT/INDENT — a header's NEWLINE and its block's
   * INDENT come from two scans at the same position. */
  lexer->mark_end(lexer);

  bool found_end_of_line = false;
  uint16_t indent_length = 0;
  int32_t first_comment_indent_length = -1;

  for (;;) {
    if (lexer->lookahead == '\n') {
      found_end_of_line = true;
      indent_length = 0;
      skip(lexer);
    } else if (lexer->lookahead == ' ') {
      indent_length++;
      skip(lexer);
    } else if (lexer->lookahead == '\r' || lexer->lookahead == '\f') {
      indent_length = 0;
      skip(lexer);
    } else if (lexer->lookahead == '\t') {
      indent_length += 8;  /* tabs count as 8 columns (upstream semantics) */
      skip(lexer);
    } else if (lexer->lookahead == '#') {
      /* a comment only counts as a line ending once we have already crossed
       * an EOL — a trailing comment after an expression is NOT a NEWLINE
       * (the scanner declines; the grammar's comment extra handles it) */
      if (!found_end_of_line) {
        return false;
      }
      if (first_comment_indent_length == -1) {
        first_comment_indent_length = (int32_t)indent_length;
      }
      while (lexer->lookahead && lexer->lookahead != '\n') {
        skip(lexer);
      }
      skip(lexer);
      indent_length = 0;
    } else if (lexer->lookahead == '\\') {
      /* a backslash continuation keeps the logical line open: `\` + newline
       * is skipped as part of the same line (no NEWLINE emitted) */
      skip(lexer);
      if (lexer->lookahead == '\r') {
        skip(lexer);
      }
      if (lexer->lookahead == '\n' || lexer->eof(lexer)) {
        skip(lexer);
      } else {
        return false;
      }
    } else if (lexer->eof(lexer)) {
      indent_length = 0;
      found_end_of_line = true;
      break;
    } else {
      break;
    }
  }

  if (found_end_of_line) {
    if (stack->count > 0) {
      uint16_t current = stack_top(stack);
      if (valid_symbols[INDENT] && indent_length > current) {
        stack_push(stack, indent_length);
        lexer->result_symbol = INDENT;
        return true;
      }
      /* the comment guard: delay the DEDENT past comments whose indent
       * matches the current block (upstream's first_comment_indent_length) */
      if (valid_symbols[DEDENT] && indent_length < current &&
          first_comment_indent_length < (int32_t)current) {
        stack_pop(stack);
        lexer->result_symbol = DEDENT;
        return true;
      }
    }
    if (valid_symbols[NEWLINE]) {
      lexer->result_symbol = NEWLINE;
      return true;
    }
  }
  return false;
}
