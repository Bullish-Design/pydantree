#include "tree_sitter/parser.h"
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum TokenType { NEWLINE, INDENT, DEDENT };

typedef struct { int32_t *columns; uint32_t count; uint32_t capacity; } IndentStack;
static void stack_push(IndentStack *s, int32_t c) {
  if (s->count == s->capacity) { s->capacity *= 2; s->columns = realloc(s->columns, s->capacity * sizeof(int32_t)); }
  s->columns[s->count++] = c;
}
static int32_t stack_top(const IndentStack *s) { return s->columns[s->count - 1]; }
static int32_t stack_pop(IndentStack *s) { return s->columns[--s->count]; }
static void advance(TSLexer *l) { l->advance(l, false); }
static void skip(TSLexer *l) { l->advance(l, true); }

void *tree_sitter_pymini_external_scanner_create(void) {
  IndentStack *s = calloc(1, sizeof(IndentStack));
  s->capacity = 8; s->columns = malloc(8 * sizeof(int32_t)); s->count = 1; s->columns[0] = 0;
  return s;
}
void tree_sitter_pymini_external_scanner_destroy(void *p) {
  IndentStack *s = (IndentStack *)p; free(s->columns); free(s);
}
unsigned tree_sitter_pymini_external_scanner_serialize(void *p, char *b) {
  IndentStack *s = (IndentStack *)p;
  uint32_t sz = s->count * sizeof(int32_t);
  if (sz > TREE_SITTER_SERIALIZATION_BUFFER_SIZE) sz = TREE_SITTER_SERIALIZATION_BUFFER_SIZE;
  memcpy(b, s->columns, sz); return sz;
}
void tree_sitter_pymini_external_scanner_deserialize(void *p, const char *b, unsigned n) {
  IndentStack *s = (IndentStack *)p;
  if (n > 0) { s->count = n / sizeof(int32_t); memcpy(s->columns, b, n); }
}

bool tree_sitter_pymini_external_scanner_scan(void *payload, TSLexer *lexer,
                                              const bool *valid_symbols) {
  IndentStack *stack = (IndentStack *)payload;
  bool want_indent = valid_symbols[NEWLINE] || valid_symbols[INDENT] ||
                     valid_symbols[DEDENT];

  if (want_indent) {
    /* mark the token end at the START: the newline is SKIPPED (never part of
     * the emitted token), so the next scan call re-crosses it and can emit
     * DEDENT/INDENT with a freshly measured column — the canonical two-call
     * cadence (NEWLINE first, then DEDENT/INDENT at the same position). */
    lexer->mark_end(lexer);

    /* skip leading whitespace of the current position */
    while (lexer->lookahead == ' ' || lexer->lookahead == '\t') {
      skip(lexer);
    }

    bool newline = false;
    if (lexer->eof(lexer)) {
      newline = true;
    } else if (lexer->lookahead == '\n') {
      newline = true;
      skip(lexer); /* skipped, not advanced — see above */
    }

    /* comment-only lines still count as a newline (Python semantics) */
    while (lexer->lookahead == '#') {
      while (lexer->lookahead != '\n' && !lexer->eof(lexer)) {
        skip(lexer);
      }
      if (lexer->eof(lexer)) {
        newline = true;
        break;
      }
      skip(lexer);
      newline = true;
    }

    if (newline) {
      /* measure the current line's indentation column */
      int32_t column = 0;
      while (lexer->lookahead == ' ' || lexer->lookahead == '\t') {
        column++;
        skip(lexer);
      }
      if (column > stack_top(stack) && valid_symbols[INDENT]) {
        stack_push(stack, column);
        lexer->result_symbol = INDENT;
        return true;
      }
      if (column < stack_top(stack) && valid_symbols[DEDENT]) {
        stack_pop(stack);
        lexer->result_symbol = DEDENT;
        return true;
      }
      /* a trailing newline at EOF still yields the NEWLINE (Python does) —
       * the parser then sees EOF and the block state flushes DEDENTs */
      if (valid_symbols[NEWLINE]) {
        lexer->result_symbol = NEWLINE;
        return true;
      }
    }
  }

  /* ordinary token path: whitespace, newlines and comments are skipped (the
   * newline reaches here only when NO NEWLINE/INDENT/DEDENT is valid, so it
   * is a blank line — skipped, Python semantics); the lexer produces the
   * real token */
  while (lexer->lookahead == ' ' || lexer->lookahead == '\t' ||
         lexer->lookahead == '\n' || lexer->lookahead == '\r') {
    skip(lexer);
  }
  if (lexer->lookahead == '#') {
    while (lexer->lookahead != '\n' && !lexer->eof(lexer)) {
      skip(lexer);
    }
  }
  return false;
}
