"""Probe the D13 shipped type-contract and type-gate behavior."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import get_args, get_type_hints

from pydantree_sitter.spec import OutputModel
from pydantree_sitter_grammar.expressions import _as_op
from pydantree_sitter_grammar.ir import Rule


def main() -> None:
    type_result = subprocess.run(
        ["ty", "check", "src"],
        capture_output=True,
        text=True,
        check=False,
    )
    as_op_return = get_type_hints(_as_op)["return"]
    rule_union = get_args(Rule)[0]
    output_model_hints = get_type_hints(OutputModel, include_extras=True)
    report = {
        "d13_type_contract": {
            "as_op_return_matches_rule_union": as_op_return == rule_union,
            "as_op_return": str(as_op_return),
            "output_model_declares_match_spec": "_match_spec" in output_model_hints,
            "output_model_match_spec": str(output_model_hints.get("_match_spec")),
        },
        "d13_type_gate": {
            "command": "ty check src",
            "returncode": type_result.returncode,
            "stdout": type_result.stdout,
            "stderr": type_result.stderr,
            "mypy_available": shutil.which("mypy") is not None,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
