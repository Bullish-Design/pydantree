#!/usr/bin/env bash
# unclosed.sh — a hand-authored sample exercising bash's lenient-EOF heredoc:
# an unclosed body is closed at EOF. The grammar emits a MISSING heredoc_end
# node (empty text), so `end` materializes as "" (not None — the node exists,
# it is just missing).
cat <<BODY
unclosed body
