/* pydantree_sitter_grammar scanner library seed #2: the HEREDOC scanner (Phase 6).

 * Canonical mechanism (mirrors the ecosystem's heredoc scanners): two
 * externals — HEREDOC_START (`<<` + the delimiter word, captured into the
 * scanner state) and HEREDOC_BODY (the content lines, ending at the END of
 * the delimiter line — the token INCLUDES the delimiter line, like bash's
 * heredoc nodes; the grammar's trailing NEWLINE token consumes the newline).
 *
 * Grammar shape (hmini):
 *
 *   g.external(tg.tok("HEREDOC_START"), tg.tok("HEREDOC_BODY"))
 *   g.rule("heredoc_stmt",
 *          tg.seq(tg.tok("HEREDOC_START"), tg.tok("HEREDOC_BODY"),
 *                 tg.tok("NEWLINE")))
 *
 * The scanner's cadence: the newline ending the `<< TAG` line is SKIPPED
 * (whitespace — the body token starts on the first content line); each
 * content line is consumed as part of the token; a line exactly equal to the
 * captured delimiter ENDS the token (mark_end after the line's content, so
 * the newline stays for the grammar). EOF without a delimiter ends the token
 * at EOF (lenient, like the indentation seed). The delimiter line is compared
 * exactly (no trailing whitespace trimming) — documented strictness.
 */

#include "tree_sitter/parser.h"
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

enum TokenType { HEREDOC_START, HEREDOC_BODY };

typedef struct {
  char delim[64];
  unsigned delim_len;
  char line[128];
} Scanner;

void *tree_sitter_hmini_external_scanner_create(void) {
  Scanner *s = calloc(1, sizeof(Scanner));
  return s;
}
void tree_sitter_hmini_external_scanner_destroy(void *p) { free(p); }
unsigned tree_sitter_hmini_external_scanner_serialize(void *p, char *b) {
  Scanner *s = (Scanner *)p;
  memcpy(b, &s->delim_len, sizeof(unsigned));
  memcpy(b + sizeof(unsigned), s->delim, s->delim_len);
  return sizeof(unsigned) + s->delim_len;
}
void tree_sitter_hmini_external_scanner_deserialize(void *p, const char *b, unsigned n) {
  Scanner *s = (Scanner *)p;
  if (n >= sizeof(unsigned)) {
    memcpy(&s->delim_len, b, sizeof(unsigned));
    if (s->delim_len >= sizeof(s->delim)) s->delim_len = sizeof(s->delim) - 1;
    memcpy(s->delim, b + sizeof(unsigned), s->delim_len);
    s->delim[s->delim_len] = 0;
  }
}

static bool scan_heredoc_start(Scanner *s, TSLexer *lexer) {
  /* `<<` [spaces] delimiter-word */
  if (lexer->lookahead != '<') return false;
  lexer->advance(lexer, false);
  if (lexer->lookahead != '<') return false;
  lexer->advance(lexer, false);
  while (lexer->lookahead == ' ' || lexer->lookahead == '\t') {
    lexer->advance(lexer, false);
  }
  unsigned len = 0;
  while (!lexer->eof(lexer) && len < sizeof(s->delim) - 1 &&
         lexer->lookahead != '\n' && lexer->lookahead != ' ' &&
         lexer->lookahead != '\t') {
    s->delim[len++] = (char)lexer->lookahead;
    lexer->advance(lexer, false);
  }
  s->delim[len] = 0;
  s->delim_len = len;
  if (len == 0) return false;
  lexer->result_symbol = HEREDOC_START;
  return true;
}

static bool scan_heredoc_body(Scanner *s, TSLexer *lexer) {
  /* the newline ending the `<< TAG` line is skipped — the body token starts
   * on the first content line (like the indentation seed's cadence) */
  if (lexer->lookahead == '\n') {
    lexer->advance(lexer, true);
  }
  while (true) {
    if (lexer->eof(lexer)) {
      lexer->mark_end(lexer);
      lexer->result_symbol = HEREDOC_BODY;
      return true;
    }
    /* read one line into the buffer */
    unsigned len = 0;
    while (!lexer->eof(lexer) && lexer->lookahead != '\n') {
      if (len < sizeof(s->line) - 1) s->line[len++] = (char)lexer->lookahead;
      lexer->advance(lexer, false);
    }
    s->line[len] = 0;
    if (s->delim_len > 0 && strcmp(s->line, s->delim) == 0) {
      /* the delimiter line ENDS the token (its newline stays for the
       * grammar's NEWLINE token) */
      lexer->mark_end(lexer);
      lexer->result_symbol = HEREDOC_BODY;
      return true;
    }
    if (lexer->eof(lexer)) {
      lexer->mark_end(lexer);
      lexer->result_symbol = HEREDOC_BODY;
      return true;
    }
    lexer->advance(lexer, false);  /* the newline — part of the body */
  }
}

static void skip_space(TSLexer *lexer) {
  while (lexer->lookahead == ' ' || lexer->lookahead == '\t') {
    lexer->advance(lexer, true);
  }
}

bool tree_sitter_hmini_external_scanner_scan(void *payload, TSLexer *lexer,
                                             const bool *valid_symbols) {
  Scanner *s = (Scanner *)payload;
  if (lexer->eof(lexer)) return false;
  /* the lexer can call the scanner mid-whitespace; and both externals can be
   * valid in ONE parser state (after an identifier), so skip spaces first,
   * then let the source disambiguate: a `<<` is always a START */
  skip_space(lexer);
  if (valid_symbols[HEREDOC_START] && lexer->lookahead == '<') {
    return scan_heredoc_start(s, lexer);
  }
  if (valid_symbols[HEREDOC_BODY]) {
    return scan_heredoc_body(s, lexer);
  }
  return false;
}
