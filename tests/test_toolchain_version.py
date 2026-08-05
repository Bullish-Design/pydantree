import re
import subprocess

import pytest

SUPPORTED = {"0.25"}  # major.minor ranges the conflict/schema code is verified against


def _cli_mm():
    out = subprocess.run(["tree-sitter", "--version"], capture_output=True, text=True)
    m = re.search(r"(\d+)\.(\d+)\.\d+", out.stdout or out.stderr)
    return f"{m.group(1)}.{m.group(2)}" if m else None


@pytest.mark.toolchain
def test_cli_version_is_supported():
    mm = _cli_mm()
    assert mm in SUPPORTED, (
        f"tree-sitter CLI {mm} is outside the verified set {SUPPORTED}; "
        f"the conflict-report parser (conflicts.py) and the byte-for-byte "
        f"schema test are CLI-version-coupled — see REVIEW 018 §1.4/B7"
    )
