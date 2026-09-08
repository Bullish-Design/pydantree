"""Small regression tests for import and packaging contract hygiene."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_grammar_modules_compile_without_syntax_warnings():
    modules = [
        ROOT / "src" / "pydantree_sitter_grammar" / "builder.py",
        ROOT / "src" / "pydantree_sitter_grammar" / "patterns.py",
    ]
    result = subprocess.run(
        [sys.executable, "-W", "error::SyntaxWarning", "-m", "py_compile",
         *(str(path) for path in modules)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
