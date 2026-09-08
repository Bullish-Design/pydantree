"""Keep the executable Python examples in the typed-node documentation fresh."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = (ROOT / "README.md", ROOT / "docs" / "user-guide.md")


def _python_blocks(text: str):
    return re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)


def test_documented_python_blocks_compile():
    for path in DOCS:
        for index, block in enumerate(_python_blocks(path.read_text()), 1):
            ast.parse(block, filename=f"{path.name}:{index}")
