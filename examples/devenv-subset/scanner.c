/* Product B — the external scanner for the devenv-subset grammar.
 *
 * Two externals: STRING_FRAGMENT (plain `"..."` bodies) and
 * INDENTED_STRING_FRAGMENT (`''...''` bodies). Both stop at the interpolation
 * start `${` (the grammar parses the interpolation) and mark the token end
 * BEFORE each stop, so the fragment never swallows the delimiter; the
 * indented branch also distinguishes the closing `''` from the ESCAPES
 * `''$` and `'''` (kept as content — `''${...}` in a real config is literal
 * text to the bash that eventually runs, so the raw string text must keep
 * it).
 *
 * This is the same external-scanner mechanism the upstream tree-sitter-nix
 * grammar uses — but ~40 lines instead of 7.6 KB, and position-stable under
 * the tree-sitter 0.26 runtime (the Phase-9 finding: upstream's scanner
 * corrupts node start-points on large multiline-string-heavy files; this
 * one does not).
 */
#include "tree_sitter/parser.h"
#include <stdbool.h>

enum TokenType {
  STRING_FRAGMENT,
  INDENTED_STRING_FRAGMENT,
};

static void advance(TSLexer *lexer) { lexer->advance(lexer, false); }

bool tree_sitter_devenv_external_scanner_scan(void *payload, TSLexer *lexer,
                                              const bool *valid_symbols) {
  /* both fragments valid at once happens only during error recovery (the
   * upstream scanner's note) — refuse so recovery doesn't eat content */
  if (valid_symbols[STRING_FRAGMENT] && valid_symbols[INDENTED_STRING_FRAGMENT]) {
    return false;
  }

  if (valid_symbols[STRING_FRAGMENT]) {
    lexer->result_symbol = STRING_FRAGMENT;
    for (bool has_content = false;; has_content = true) {
      lexer->mark_end(lexer); /* the token ends BEFORE the stop */
      if (lexer->eof(lexer)) {
        return false; /* unterminated string: refuse */
      }
      if (lexer->lookahead == '"') {
        return has_content; /* closing delimiter — not consumed */
      }
      if (lexer->lookahead == '$') {
        advance(lexer);
        if (lexer->lookahead == '{') {
          return has_content; /* interpolation — the grammar parses it */
        }
        continue; /* a lone $ is content */
      }
      if (lexer->lookahead == '\\') {
        advance(lexer); /* the escaped char is content too */
        if (!lexer->eof(lexer)) {
          advance(lexer);
        }
        continue;
      }
      advance(lexer);
    }
  }

  if (valid_symbols[INDENTED_STRING_FRAGMENT]) {
    lexer->result_symbol = INDENTED_STRING_FRAGMENT;
    for (bool has_content = false;; has_content = true) {
      lexer->mark_end(lexer);
      if (lexer->eof(lexer)) {
        return false;
      }
      if (lexer->lookahead == '$') {
        advance(lexer);
        if (lexer->lookahead == '{') {
          return has_content; /* interpolation — the grammar parses it */
        }
        continue;
      }
      if (lexer->lookahead == '\'') {
        advance(lexer); /* first quote */
        if (lexer->lookahead == '\'') {
          advance(lexer); /* second quote */
          if (lexer->lookahead == '$' || lexer->lookahead == '\'') {
            advance(lexer); /* ''$ or ''' — the escape's third char is
                             * content; the string continues */
            continue;
          }
          return has_content; /* plain '' — the closing delimiter (the
                               * mark_end is before it) */
        }
        continue; /* a lone quote is content */
      }
      advance(lexer);
    }
  }

  return false;
}

void *tree_sitter_devenv_external_scanner_create(void) { return NULL; }

void tree_sitter_devenv_external_scanner_destroy(void *payload) {}

unsigned tree_sitter_devenv_external_scanner_serialize(void *payload,
                                                       char *buffer) {
  return 0;
}

void tree_sitter_devenv_external_scanner_deserialize(void *payload,
                                                     const char *buffer,
                                                     unsigned length) {}
