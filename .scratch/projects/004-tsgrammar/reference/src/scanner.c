/*
 * Minimal external scanner for the kitsink reference grammar.
 *
 * The grammar declares one external token, TERM (an external token is one the
 * lexer cannot express as a regex — here, a `#` "sigil" statement prefix).
 * This scanner provides the standard five-function external-scanner API
 * (0.25 signature: `scan` takes `const bool *valid_symbols`).
 *
 * Pipeline note: when a grammar declares `externals`, the generated parser.c
 * only *declares* these symbols; a scanner.c implementing them must be
 * compiled alongside. Without one, dlopen fails with an undefined symbol.
 *
 * Runtime note: the external scanner is invoked BEFORE the main lexer skips
 * whitespace, so it must skip leading whitespace itself (advance with
 * skip=true) — the standard scanner pattern.
 */
#include <ctype.h>
#include "tree_sitter/parser.h"

enum TokenType { TERM };

void *tree_sitter_kitsink_external_scanner_create(void) { return NULL; }

void tree_sitter_kitsink_external_scanner_destroy(void *p) { (void)p; }

unsigned tree_sitter_kitsink_external_scanner_serialize(void *p, char *buffer) {
  (void)p; (void)buffer;
  return 0;
}

void tree_sitter_kitsink_external_scanner_deserialize(void *p, const char *buffer, unsigned n) {
  (void)p; (void)buffer; (void)n;
}

bool tree_sitter_kitsink_external_scanner_scan(void *p, TSLexer *lexer, const bool *valid_symbols) {
  (void)p;
  if (!valid_symbols[TERM]) return false;

  /* skip leading whitespace (the scanner runs before extras are lexed) */
  while (isspace(lexer->lookahead)) {
    lexer->advance(lexer, true);
  }

  if (lexer->lookahead != '#') return false;
  lexer->advance(lexer, false);   /* consume '#' */
  lexer->result_symbol = TERM;
  return true;
}
