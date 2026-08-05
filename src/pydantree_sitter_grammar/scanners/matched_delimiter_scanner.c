/* pydantree_sitter_grammar scanner library seed #3: the matched-delimiter scanner (Phase 6).

 * Canonical mechanism (the tree-sitter docs' external-scanner example): a
 * BALANCED external token that reads a `(...)` group with ARBITRARY nesting
 * as ONE token — the lexer counts paren depth and the token ends at the
 * matching close. The grammar never sees the inner parens.
 *
 * Grammar shape (dmini):
 *
 *   g.external(tg.tok("BALANCED"))
 *   g.rule("group", tg.tok("BALANCED"))
 *
 * Strictness: an unbalanced open at EOF is a scan failure (the token is not
 * emitted) — the parser falls back to other rules rather than silently
 * swallowing a malformed group.
 */

#include "tree_sitter/parser.h"
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>

enum TokenType { BALANCED };

bool tree_sitter_dmini_external_scanner_scan(void *payload, TSLexer *lexer,
                                             const bool *valid_symbols) {
  if (!valid_symbols[BALANCED]) return false;
  /* the lexer can call the scanner mid-whitespace — skip it first */
  while (lexer->lookahead == ' ' || lexer->lookahead == '\t' ||
         lexer->lookahead == '\n') {
    lexer->advance(lexer, true);
  }
  if (lexer->lookahead != '(') return false;
  int depth = 0;
  while (true) {
    if (lexer->eof(lexer)) {
      /* unbalanced open parens at EOF: refuse the token (strict) */
      return false;
    }
    if (lexer->lookahead == '(') {
      depth++;
    } else if (lexer->lookahead == ')') {
      depth--;
      lexer->advance(lexer, false);
      if (depth == 0) break;
      continue;
    }
    lexer->advance(lexer, false);
  }
  /* the token spans from the opening '(' through the matching ')' */
  lexer->mark_end(lexer);
  lexer->result_symbol = BALANCED;
  return true;
}

void *tree_sitter_dmini_external_scanner_create(void) { return NULL; }
void tree_sitter_dmini_external_scanner_destroy(void *p) { (void)p; }
unsigned tree_sitter_dmini_external_scanner_serialize(void *p, char *b) {
  (void)p; (void)b; return 0;
}
void tree_sitter_dmini_external_scanner_deserialize(void *p, const char *b, unsigned n) {
  (void)p; (void)b; (void)n;
}
