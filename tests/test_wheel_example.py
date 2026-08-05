"""The wheel-extract example: a TOOLCHAIN-FREE live fixture with a committed
per-step transcript oracle (Review 020 §3 recommendation).

The other oracle tests (test_oracles.py) need the tree-sitter CLI + gcc to
build grammar bundles; THIS one runs on a community WHEEL (tree-sitter-python)
in any env with pydantree_sitter + tree-sitter-python installed — and it is
deliberately NOT toolchain-marked. The committed transcript.txt is the
per-step oracle: the example's stdout must match it byte-for-byte, so the
developer can see exactly what is being done at each step and the example
cannot rot silently.

Regenerate the oracle (after eyeballing the diff):

    devenv shell -- python examples/wheel-extract/extract.py --update
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_python")

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "wheel-extract"
EXTRACT = EXAMPLE / "extract.py"
TRANSCRIPT = EXAMPLE / "transcript.txt"


def test_wheel_example_runs_and_matches_the_transcript_oracle():
    # the subprocess must resolve src/ live (the devenv .pth may be absent
    # in a plain shell) — PYTHONPATH is environment plumbing, NOT toolchain
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO / "src"), env.get("PYTHONPATH", "")])
    proc = subprocess.run([sys.executable, str(EXTRACT)],
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # the committed per-step transcript is the oracle: this run's stdout must
    # equal it byte-for-byte (regenerate with --update after eyeballing)
    transcript = TRANSCRIPT.read_text()
    assert proc.stdout == transcript


def test_wheel_example_transcript_is_a_real_per_step_narrative():
    """The oracle is a per-step narrative, not just final data."""
    transcript = TRANSCRIPT.read_text()
    for header in ("step 1: bind", "step 2: parse", "step 3: extract",
                   "step 4: self-check", "step 5: the committed"):
        assert header in transcript, header
    # step 1 shows the derived queries (no build anywhere)
    assert "Function.compiled_source()" in transcript
    assert "@__anchor__" in transcript
    # step 2 shows the CST with field names
    assert "return_type=type" in transcript
    # step 3 shows the typed rows with source lines
    assert "Function 'greet' -> 'str' at line 8" in transcript
    assert "Assignment 'answer' = '42' at line 11" in transcript
    # step 4 embeds the ground-truth self-check
    assert "all rows match the hand-written ground truth" in transcript


def test_wheel_example_ground_truth_is_embedded_in_the_oracle():
    """The hand-written ground truth and the transcript agree (the example
    self-checks internally, and the transcript captures that check)."""
    import json
    truth = json.loads((EXAMPLE / "ground_truth.json").read_text())
    transcript = TRANSCRIPT.read_text()
    for f in truth["functions"]:
        assert f"Function {f['name']!r} -> {f['return_type']!r} " \
               f"at line {f['line']}" in transcript
    for a in truth["assignments"]:
        assert f"Assignment {a['target']!r} = {a['value']!r} " \
               f"at line {a['line']}" in transcript
