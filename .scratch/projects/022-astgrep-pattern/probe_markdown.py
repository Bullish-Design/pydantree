"""What does ast-grep's built-in markdown actually give us? (the Obsidian question)

ast-grep ships `markdown` and `md`. The question is not whether it parses,
but WHAT it exposes — because Obsidian's syntax is mostly INLINE, and
tree-sitter-markdown is a two-parser design whose block half leaves inline
content opaque.
"""
from __future__ import annotations

import json
import pathlib
import sys

from ast_grep_py import SgRoot

from pydantree_sitter.agreement import char_to_byte_table

OUT = pathlib.Path(__file__).parent / "evidence" / "markdown.json"

DOC = """---
tags: [project, active]
---

# Café [[Target#Heading]]

Paragraph pré [[Target]] [[Target|Alias]] [[Target#^block]]
with ![[Embed.png]] #tag #nested/tag key:: value ==highlight==
%%comment%% ^abc123 and [[Café]] inside.

> [!note] Callout [[Quoted]]
> Body pré ^quoteid.
>
> [!warning]- Warning [[Warned]]

- [ ] tâche [[Task]]
- [x] done #checked

```python
def f(x): return x
```
"""

BLOCK_KINDS = (
    "atx_heading", "paragraph", "list_item", "block_quote",
    "task_list_marker_checked", "task_list_marker_unchecked",
)


def _range(node, table):
    """Return measured character and absolute UTF-8 byte ranges."""
    point = node.range()
    start_char = point.start.index
    end_char = point.end.index
    return {
        "character": {"start": start_char, "end": end_char},
        "byte": {"start": table[start_char], "end": table[end_char]},
    }


def _walk(node, ancestors=()):
    """Yield nodes with their measured block ancestor path."""
    block = node.kind() if node.kind() in BLOCK_KINDS else None
    block_ancestors = ancestors + ((block,) if block else ())
    yield node, block_ancestors
    for child in node.children():
        yield from _walk(child, block_ancestors)


def main() -> int:
    root = SgRoot(DOC, "markdown").root()
    table = char_to_byte_table(DOC)
    kinds = set()
    stack = [root]
    while stack:
        n = stack.pop()
        kinds.add(n.kind())
        stack.extend(n.children())

    walked = list(_walk(root))
    blocks = []
    for node, ancestors in walked:
        if node.kind() in BLOCK_KINDS:
            measured = _range(node, table)
            blocks.append({
                "kind": node.kind(),
                "text": node.text(),
                **measured,
                "block_ancestors": list(ancestors),
                "direct_children": [child.kind() for child in node.children()],
            })

    inline_nodes = []
    for node, ancestors in walked:
        if node.kind() != "inline":
            continue
        measured = _range(node, table)
        start_char = measured["character"]["start"]
        end_char = measured["character"]["end"]
        inline_nodes.append({
            "kind": node.kind(),
            "block_ancestors": list(ancestors),
            "nearest_block": ancestors[-1] if ancestors else None,
            "text": node.text(),
            "fragment": DOC[start_char:end_char],
            **measured,
            "direct_children": [child.kind() for child in node.children()],
        })

    marker_nodes = [block for block in blocks
                    if block["kind"].startswith("task_list_marker_")]
    report = {
        "source": DOC,
        "all_kinds": sorted(kinds),
        # the block half is rich and useful
        "block_structure_available": {
            k: len(root.find_all(kind=k)) for k in
            ["section", "atx_heading", "paragraph", "list", "list_item",
             "block_quote", "fenced_code_block", "minus_metadata",
             "task_list_marker_checked", "task_list_marker_unchecked"]
        },
        # ...and the inline half is not parsed AT ALL
        "inline_nodes_are_opaque": {
            "inline_node_count": len(inline_nodes),
            "kinds_inside_inline_are_only_punctuation":
                not ({"link", "emphasis", "strong_emphasis", "inline_link",
                      "shortcut_link", "wiki_link", "tag"} & kinds),
        },
        "block_nodes": blocks,
        "inline_nodes": inline_nodes,
        "task_list_marker_nodes": marker_nodes,
        "non_ascii_offset_checks": [
            {
                "fragment": item["fragment"],
                "character_start": item["character"]["start"],
                "byte_start": item["byte"]["start"],
                "source_slice": DOC.encode("utf-8")[
                    item["byte"]["start"]:item["byte"]["end"]
                ].decode("utf-8"),
            }
            for item in inline_nodes if any(ord(c) > 127 for c in
                                            item["fragment"])
        ],
        "block_level_patterns_work": {
            "# $TITLE": len(root.find_all(pattern="# $TITLE")),
            "- $ITEM": len(root.find_all(pattern="- $ITEM")),
        },
        "obsidian_syntax_addressable": {
            "wikilink": "wiki_link" in kinds,
            "embed": False,
            "tag": "tag" in kinds,
            "callout": "callout" in kinds,
        },
    }
    OUT.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
