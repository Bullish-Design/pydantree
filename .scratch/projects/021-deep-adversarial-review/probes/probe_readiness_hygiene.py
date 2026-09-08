"""Probe D14, D16, and D18 readiness-hygiene contracts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from pydantree_sitter.errors import BundleError
from pydantree_sitter.loader import load_bundle

ROOT = Path(__file__).resolve().parents[4]


def main() -> None:
    modules = [
        ROOT / "src" / "pydantree_sitter_grammar" / "builder.py",
        ROOT / "src" / "pydantree_sitter_grammar" / "patterns.py",
    ]
    compile_result = subprocess.run(
        [sys.executable, "-W", "error::SyntaxWarning", "-m", "py_compile",
         *(str(path) for path in modules)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "bundle"
        bundle.mkdir()
        (bundle / "tree-sitter.json").write_text(json.dumps({
            "bundle_format": -7,
            "name": "cfg",
            "artifact": "grammar.so",
        }))
        (bundle / "grammar.so").write_bytes(b"not a real .so")
        try:
            load_bundle(bundle)
        except BundleError as exc:
            bundle_error = {
                "class": type(exc).__name__,
                "message": str(exc).replace(tmp, "<tmp>"),
            }
        else:
            bundle_error = {"class": None, "message": None}

    docs = {
        "readme_avoids_stale_count": "272 green" not in (
            ROOT / "README.md").read_text(),
        "development_avoids_stale_count": "265 green" not in (
            ROOT / "docs" / "development.md").read_text(),
        "codegen_describes_runtime_module": "runnable Python module" in (
            ROOT / "docs" / "user-guide.md").read_text(),
        "field_nested_shape_error_documented": "field-mode nested records"
        in (ROOT / "docs" / "user-guide.md").read_text(),
        "phase_022_listed": "| 022 |" in (
            ROOT / "docs" / "README.md").read_text(),
    }
    report = {
        "d14_compile_without_syntax_warnings": {
            "returncode": compile_result.returncode,
            "stderr": compile_result.stderr,
        },
        "d16_negative_bundle_format": bundle_error,
        "d18_documentation_checks": docs,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
