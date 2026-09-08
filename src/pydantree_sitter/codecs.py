"""Value codecs used by generated node classes."""

from __future__ import annotations

import json
from typing import Any


def unescape_json(text: str) -> str:
    """Decode JSON string escapes, including lenient raw-newline input."""
    try:
        if text.startswith('"') and text.endswith('"') and len(text) >= 2:
            return json.loads(text)
        return json.loads('"' + text + '"')
    except ValueError:
        pass
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        text = text[1:-1]
    out: list[str] = []
    i = 0
    mapping = {"n": "\n", "t": "\t", "r": "\r", '"': '"',
               "\\": "\\", "b": "\b", "f": "\f", "/": "/"}
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt in mapping:
                out.append(mapping[nxt])
                i += 2
                continue
            if nxt == "u" and i + 5 <= len(text):
                try:
                    out.append(chr(int(text[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            out.append(text[i])
            i += 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


class JsonString:
    """Mixin for a node whose source text is a JSON string literal."""

    def __value__(self: Any) -> str:
        return unescape_json((self._node.text or b"").decode("utf-8", "replace"))
