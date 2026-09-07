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

OUT = pathlib.Path(__file__).parent / "evidence" / "markdown.json"

DOC = """---
tags: [project, active]
---

# Project 022

Text with a [[Wiki Link]], an ![[Embed.png]] and a #tag/nested.
A standard [link](http://x) and *emphasis*.

> [!note] Callout title
> Body of the callout.

- [ ] task one
- [x] task two

```python
def f(x): return x
```
"""


def main() -> int:
    root = SgRoot(DOC, "markdown").root()
    kinds = set()
    stack = [root]
    while stack:
        n = stack.pop()
        kinds.add(n.kind())
        stack.extend(n.children())

    inline = [n.text() for n in root.find_all(kind="inline")]
    report = {
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
            "inline_node_count": len(inline),
            "kinds_inside_inline_are_only_punctuation":
                not ({"link", "emphasis", "strong_emphasis", "inline_link",
                      "shortcut_link", "wiki_link", "tag"} & kinds),
        },
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
