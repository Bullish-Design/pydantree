#!/usr/bin/env bash
# configure.sh — a realistic hand-authored sample for the extraction task.
# Ground truth (written by hand from bash's semantics, BEFORE the models):
#   functions:        say (17), die (21), log (26)  [top-level only]
#   assignments:      PREFIX="/usr/local" (13), DEBUG=0 (14), LOG_LEVEL="info" (15),
#                     INSTALLER_NAME="pydantree-demo" (29), LOCAL_INSTALL=yes (51)
#                     — NOT export PATH=... (28: wrapped by export_command)
#   heredocs:         <<EOF (33), <<-'CONFIG' (38), <<'RAW' (43), 3<<FDBODY (47)
#   optional capture: log has a redirect (>>app.log); say/die do not
set -euo pipefail

# --- configuration ---
PREFIX="/usr/local"
DEBUG=0
LOG_LEVEL="info"

say() {                        # posix function form
  echo "[say] $1"
}

function die {                 # function-keyword form
  echo "fatal: $1" >&2
  exit 1
}

log() { echo hi; } >>app.log   # function WITH a redirect (optional capture)

export PATH="$PREFIX/bin:$PATH"
INSTALLER_NAME="pydantree-demo"

say "starting"

cat <<EOF
Welcome to $INSTALLER_NAME
prefix: $PREFIX
EOF

cat <<-'CONFIG'
# generated config
debug=0
CONFIG

cat <<'RAW'
do not expand $HOME
RAW

cat 3<<FDBODY
descriptor body
FDBODY

LOCAL_INSTALL=yes
