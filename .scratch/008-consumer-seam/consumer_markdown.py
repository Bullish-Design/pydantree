"""Run 2 (markdown rehearsal) — the community seam over tree-sitter-markdown,
B-free. BLOCK + INLINE elements, as requested.

Consumes the real tree-sitter-markdown (block) and tree-sitter-markdown-inline
bundles — built from the real grammar SOURCE via
tsgrammar.schema_tool.build_community_bundle — in a SEPARATE process where
tsgrammar is NOT importable. The schemas were derived by the community tool
(byte-for-byte with the CLI's node-types.json); the checks are active; the
rows must match the HAND-AUTHORED ground truth.

Two surfaces, both real markdown:
  * BLOCK (the block grammar): headings (the atx_heading `heading_content`
    FIELD — markdown does use fields for headings), fenced code blocks (the
    info_string / code_fence_content CHILDREN — via the Phase-6.5
    capture_kind() child-by-kind surface; markdown's fenced-code children
    have no CST fields).
  * INLINE (the inline grammar, injected-style nested parse of each `inline`
    node's text): code spans, emphasis, strong, and link destinations.

Usage: python consumer_markdown.py <block-bundle> <inline-bundle>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import tsgrammar  # noqa: F401
    print(json.dumps({"ok": False,
                      "error": "tsgrammar IS importable — B leaked"}))
    sys.exit(1)
except ModuleNotFoundError:
    pass

from tsquery import (  # noqa: E402
    Language,
    M,
    OutputModel,
    capture,
    capture_kind,
    source_meta,
)

MD_SAMPLE = """\
# Title

Some *emphasis* and **strong** and `code` and [a link](https://example.com).

## Section

```python
print(1)
```

> quoted *text*
"""

# hand-authored BEFORE the models (counted by hand over the sample): line =
# the node's start line (1-based)
HEADING_GROUND_TRUTH = [
    {"text": "Title", "line": 1},
    {"text": "Section", "line": 5},
]
FENCED_GROUND_TRUTH = [
    {"info": "python", "content": "print(1)\n", "line": 7},
]
INLINE_GROUND_TRUTH = {
    "code_spans": ["`code`"],                     # the code_span node's text
    "emphasis": ["*emphasis*", "*text*"],        # line 3 + the blockquote
    "strong": ["**strong**"],
    "links": [{"dest": "https://example.com", "line": 3}],
}


# ---- block surface --------------------------------------------------------

class Heading(OutputModel):
    """ATX headings: the `heading_content` FIELD (the only field markdown's
    block grammar has) — a descendant path (sections nest)."""

    __match__ = M("document", ..., "atx_heading")
    text: str | None = capture("heading_content")
    line: int = source_meta()


class FencedCode(OutputModel):
    """Fenced code blocks: the info_string / code_fence_content CHILDREN —
    markdown's fenced-code children have no CST fields, so this exercises the
    Phase-6.5 capture_kind() child-by-kind surface."""

    __match__ = M("document", ..., "fenced_code_block")
    info: str | None = capture_kind("info_string")
    content: str | None = capture_kind("code_fence_content")
    line: int = source_meta()


# ---- inline surface (nested parse of each `inline` node's text) -----------

class CodeSpan(OutputModel):
    __match__ = M("inline")
    text: str | None = capture_kind("code_span")


class Emphasis(OutputModel):
    __match__ = M("inline")
    text: str | None = capture_kind("emphasis")


class Strong(OutputModel):
    __match__ = M("inline")
    text: str | None = capture_kind("strong_emphasis")


class Link(OutputModel):
    __match__ = M("inline", "inline_link")
    dest: str | None = capture_kind("link_destination")


def _inline_nodes(lang, text: str) -> list:
    """The block grammar's `inline` nodes (the content the inline grammar is
    injected into by the full markdown parser — a nested parse here). Each
    carries its ORIGINAL document line (the nested parse of the node's text
    restarts line numbering)."""
    tree = lang.parse(text)
    out = []

    def walk(n):
        if n.type == "inline" and n.text.decode().strip():
            out.append((n, n.start_point.row + 1))
        for c in n.children:
            walk(c)
    walk(tree.root_node)
    return out


def main() -> int:
    block = Language.load_bundle(sys.argv[1])
    inline = Language.load_bundle(sys.argv[2])
    # the checks run BEFORE any text is parsed
    Heading.validate_with(block)
    FencedCode.validate_with(block)
    CodeSpan.validate_with(inline)
    Emphasis.validate_with(inline)
    Strong.validate_with(inline)
    Link.validate_with(inline)

    headings = [r.model_dump() for r in Heading.extract(MD_SAMPLE, language=block)]
    fenced = [r.model_dump() for r in FencedCode.extract(MD_SAMPLE, language=block)]

    code_spans: list[str] = []
    emphasis: list[str] = []
    strong: list[str] = []
    links: list[dict] = []
    for node, doc_line in _inline_nodes(block, MD_SAMPLE):
        text = node.text.decode()
        code_spans += [r.text for r in CodeSpan.extract(text, language=inline)
                       if r.text is not None]
        emphasis += [r.text for r in Emphasis.extract(text, language=inline)
                     if r.text is not None]
        strong += [r.text for r in Strong.extract(text, language=inline)
                   if r.text is not None]
        links += [{"dest": r.dest, "line": doc_line}
                  for r in Link.extract(text, language=inline)
                  if r.dest is not None]

    ok = (headings == HEADING_GROUND_TRUTH
          and fenced == FENCED_GROUND_TRUTH
          and code_spans == INLINE_GROUND_TRUTH["code_spans"]
          and emphasis == INLINE_GROUND_TRUTH["emphasis"]
          and strong == INLINE_GROUND_TRUTH["strong"]
          and links == INLINE_GROUND_TRUTH["links"])
    print(json.dumps({
        "ok": ok,
        "headings": headings,
        "fenced": fenced,
        "code_spans": code_spans,
        "emphasis": emphasis,
        "strong": strong,
        "links": links,
        "block_schema_kinds": len(block.schema.kinds()),
        "inline_schema_kinds": len(inline.schema.kinds()),
    }, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
