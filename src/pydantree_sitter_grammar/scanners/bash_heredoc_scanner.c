/* pydantree_sitter_grammar scanner library — the bash-style heredoc scanner (Phase 7,
 * adapted from tree-sitter-bash's src/scanner.c — the MULTI-heredoc case:
 * several pending delimiters queued on one command line, `<<-`
 * indent-stripped, and quoted delimiters).
 *
 * Two externals, on the hmini mechanism (Phase 6 — proven; a single BODY
 * token INCLUDES the delimiter line, bash-like; the trailing newline is the
 * grammar's own token):
 *
 *   HEREDOC_START  `<<` [`-`] [`'`|`"`] delimiter-word  — pushed onto the
 *                  pending QUEUE (delimiter + allows_indent + is_raw flags)
 *   HEREDOC_BODY   the OLDEST pending heredoc's content AND its delimiter
 *                  line (FIFO — real bash reads `cat <<A <<B` as A's body
 *                  then B's body, and the grammar consumes them in that
 *                  order); the token ends just before the newline, then the
 *                  pending heredoc is popped
 *
 * Grammar shape (bashmini):
 *
 *   g.external(tg.tok("HEREDOC_START"), tg.tok("HEREDOC_BODY"))
 *   g.rule("command", tg.repeat1(tg.choice(tg.ref("identifier"),
 *                                          tg.tok("HEREDOC_START"))))
 *   g.rule("heredoc", tg.tok("HEREDOC_BODY"))
 *   g.rule("item", tg.seq(tg.ref("command"), tg.ref("newline"),
 *                         tg.repeat(tg.ref("heredoc"))))
 *
 * The two Phase-6 gotchas are facts here: the lexer calls the scanner
 * mid-whitespace (START skips spaces first; a `<` is always a START — the
 * source disambiguates), and the delimiter comparison is exact (a line that
 * merely STARTS with the delimiter word is content, not the end). `<<-`
 * strips leading tabs from the delimiter line (bash semantics); `<<'TAG'` /
 * `<<"TAG"` quote the delimiter (the body is inert content either way in
 * this mini-grammar — no expansions modeled, the honest scope line).
 */

#include "tree_sitter/parser.h"
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

enum TokenType { HEREDOC_START, HEREDOC_BODY };

#define MAX_PENDING 8
#define MAX_DELIM 64
#define MAX_LINE 256

typedef struct {
  char delim[MAX_DELIM];
  unsigned delim_len;
  bool allows_indent;  /* `<<-`: the delimiter line may be tab-indented */
  bool is_raw;         /* `<<'TAG'` / `<<"TAG"`: quoted delimiter */
} Pending;

typedef struct {
  Pending queue[MAX_PENDING];
  unsigned front;
  unsigned count;
} Scanner;

void *tree_sitter_bashmini_external_scanner_create(void) {
  return calloc(1, sizeof(Scanner));
}
void tree_sitter_bashmini_external_scanner_destroy(void *p) { free(p); }

static Pending *peek_front(Scanner *s) {
  return s->count > 0 ? &s->queue[s->front] : NULL;
}
static void pop_front(Scanner *s) {
  if (s->count == 0) return;
  s->front = (s->front + 1) % MAX_PENDING;
  s->count--;
}

unsigned tree_sitter_bashmini_external_scanner_serialize(void *p, char *b) {
  Scanner *s = (Scanner *)p;
  unsigned n = 0;
  b[n++] = (char)s->count;
  for (unsigned i = 0; i < s->count; i++) {
    Pending *h = &s->queue[(s->front + i) % MAX_PENDING];
    if (n + 2 + h->delim_len >= TREE_SITTER_SERIALIZATION_BUFFER_SIZE) break;
    b[n++] = h->allows_indent ? 1 : 0;
    b[n++] = (char)h->delim_len;
    memcpy(b + n, h->delim, h->delim_len);
    n += h->delim_len;
  }
  return n;
}
void tree_sitter_bashmini_external_scanner_deserialize(void *p, const char *b,
                                                       unsigned len) {
  Scanner *s = (Scanner *)p;
  s->front = 0;
  s->count = 0;
  if (len == 0) return;
  unsigned n = 0;
  unsigned count = (unsigned char)b[n++];
  for (unsigned i = 0; i < count && n + 2 <= len; i++) {
    Pending *h = &s->queue[(s->front + s->count) % MAX_PENDING];
    h->allows_indent = b[n++] != 0;
    h->delim_len = (unsigned char)b[n++];
    if (h->delim_len > MAX_DELIM - 1) h->delim_len = MAX_DELIM - 1;
    if (n + h->delim_len > len) h->delim_len = len - n;
    memcpy(h->delim, b + n, h->delim_len);
    n += h->delim_len;
    h->delim[h->delim_len] = 0;
    s->count++;
  }
}

static bool scan_start(Scanner *s, TSLexer *lexer) {
  /* the lexer can call the scanner mid-whitespace (after an identifier) —
   * skip spaces first, then `<<` is always a START (the source
   * disambiguates, Phase-6 gotcha 2) */
  while (lexer->lookahead == ' ' || lexer->lookahead == '\t') {
    lexer->advance(lexer, true);
  }
  if (lexer->lookahead != '<') return false;
  lexer->advance(lexer, false);
  if (lexer->lookahead != '<') return false;
  lexer->advance(lexer, false);

  if (s->count >= MAX_PENDING) return false;  /* queue full: decline */
  Pending *h = &s->queue[(s->front + s->count) % MAX_PENDING];
  memset(h, 0, sizeof(Pending));

  if (lexer->lookahead == '-') {
    h->allows_indent = true;  /* `<<-`: the delimiter line may be indented */
    lexer->advance(lexer, false);
  }
  if (lexer->lookahead == '\'' || lexer->lookahead == '"') {
    h->is_raw = true;  /* quoted delimiter: the body is inert (no expansions
                        * modeled — the honest scope line) */
    lexer->advance(lexer, false);
  }
  while (!lexer->eof(lexer) && lexer->lookahead != '\n' &&
         lexer->lookahead != ' ' && lexer->lookahead != '\t' &&
         h->delim_len < MAX_DELIM - 1) {
    h->delim[h->delim_len++] = (char)lexer->lookahead;
    lexer->advance(lexer, false);
  }
  h->delim[h->delim_len] = 0;
  if (h->delim_len == 0) return false;
  s->count++;
  lexer->mark_end(lexer);
  lexer->result_symbol = HEREDOC_START;
  return true;
}

static bool line_is_delim(Pending *h, const char *line) {
  /* exact delimiter match; `<<-` heredocs allow leading tabs on the line */
  const char *p = line;
  if (h->allows_indent) {
    while (*p == '\t') p++;
  }
  return strcmp(p, h->delim) == 0;
}

static bool scan_body(Scanner *s, TSLexer *lexer) {
  Pending *h = peek_front(s);
  if (!h) return false;
  if (lexer->eof(lexer)) return false;

  char line[MAX_LINE];
  while (true) {
    if (lexer->eof(lexer)) {
      /* EOF without the delimiter line ends the token at EOF (lenient, like
       * the indentation seed; the pending heredoc is popped — the grammar
       * then sees the body as closed, exactly bash's unclosed-heredoc-at-EOF
       * behavior) */
      pop_front(s);
      lexer->mark_end(lexer);
      lexer->result_symbol = HEREDOC_BODY;
      return true;
    }
    /* read one line into the buffer (the delimiter comparison is exact) */
    unsigned len = 0;
    while (!lexer->eof(lexer) && lexer->lookahead != '\n') {
      if (len < MAX_LINE - 1) line[len++] = (char)lexer->lookahead;
      lexer->advance(lexer, false);
    }
    line[len] = 0;
    if (line_is_delim(h, line)) {
      /* the delimiter line ENDS the token (bash-like, the hmini mechanism);
       * its newline stays for the grammar's own newline token */
      lexer->mark_end(lexer);
      lexer->result_symbol = HEREDOC_BODY;
      pop_front(s);
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

bool tree_sitter_bashmini_external_scanner_scan(void *payload, TSLexer *lexer,
                                                const bool *valid_symbols) {
  Scanner *s = (Scanner *)payload;
  /* the lexer can call the scanner MID-WHITESPACE (after an identifier, the
   * lookahead is the space before `<<`) — START skips spaces itself, so the
   * dispatch must not gate on the raw lookahead (Phase-6 gotcha 1). */
  if (valid_symbols[HEREDOC_START]) {
    if (scan_start(s, lexer)) {
      return true;
    }
    /* fall through: START declined (not a `<<`) — but BODY may be valid in
     * the SAME parser state (Phase-6 gotcha 2: both externals valid in one
     * state after the command's newline; the source disambiguates — the
     * delimiter line is the body's end, anything else is body content). */
  }
  if (valid_symbols[HEREDOC_BODY] && s->count > 0) {
    return scan_body(s, lexer);
  }
  return false;
}
