"""Measure the ast-grep Markdown to Obsidian-inline parser handoff."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ast_grep_py import SgRoot

import pydantree_sitter as pt
from pydantree_sitter.agreement import char_to_byte_table

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import obsidian_inline
from probe_markdown import BLOCK_KINDS, DOC, _range, _walk

OUT = HERE / "evidence" / "obsidian-markdown.json"
KINDS = (
    "wiki_link", "embed", "tag", "callout_marker", "inline_field",
    "block_id", "highlight", "comment",
)
REQUIRED = {
    "wiki_link": {
        "[[Target#Heading]]", "[[Target]]", "[[Target|Alias]]",
        "[[Target#^block]]", "[[Café]]", "[[Quoted]]", "[[Task]]",
        "[[Warned]]",
    },
    "embed": {"![[Embed.png]]"},
    "tag": {"#tag", "#nested/tag", "#checked"},
    "callout_marker": {"[!note]", "[!warning]-"},
    "inline_field": {"key:: value"},
    "block_id": {"^abc123", "^quoteid"},
    "highlight": {"==highlight=="},
    "comment": {"%%comment%%"},
}


def main() -> int:
    result = obsidian_inline.build()
    bundle = result.package(HERE / "evidence" / "obsidian-inline-bundle")
    language = pt.Language.load_bundle(bundle)
    language.register_astgrep(
        name="obsidian_inline", extensions=["md"],
        meta_var_char="$", expando_char="_",
    )
    patterns = {
        kind: pt.Pattern(pt.Rule(kind=kind), language=language)
        for kind in KINDS
    }

    source_bytes = DOC.encode("utf-8")
    table = char_to_byte_table(DOC)
    root = SgRoot(DOC, "markdown").root()
    records = []
    inline_count = 0
    for node, ancestors in _walk(root):
        if node.kind() != "inline":
            continue
        inline_count += 1
        measured = _range(node, table)
        start_char = measured["character"]["start"]
        end_char = measured["character"]["end"]
        fragment = DOC[start_char:end_char]
        base_byte = measured["byte"]["start"]
        for kind, pattern in patterns.items():
            for match in pattern.find_all_rebased(
                    fragment, base_byte=base_byte):
                original = source_bytes[
                    match.span.start_byte:match.span.end_byte
                ].decode("utf-8")
                assert original == match.text
                assert base_byte <= match.span.start_byte
                assert match.span.end_byte <= measured["byte"]["end"]
                records.append({
                    "markdown_node_kind": node.kind(),
                    "markdown_block_ancestors": list(ancestors),
                    "markdown_node_character_range": measured["character"],
                    "markdown_node_byte_range": measured["byte"],
                    "inline_fragment_text": fragment,
                    "inline_match_kind": kind,
                    "match_text": match.text,
                    "absolute_byte_start": match.span.start_byte,
                    "absolute_byte_end": match.span.end_byte,
                    "original_source_slice": original,
                })

    found = {kind: set() for kind in KINDS}
    for record in records:
        text = record["match_text"]
        found[record["inline_match_kind"]].add(text.strip())
    missing = {
        kind: sorted(values - found[kind])
        for kind, values in REQUIRED.items() if values - found[kind]
    }
    assert not missing, missing

    report = {
        "source": DOC,
        "bundle": str(bundle),
        "same_artifact": patterns["wiki_link"].agreement.same_artifact,
        "markdown_block_counts": {
            kind: len(root.find_all(kind=kind))
            for kind in (*BLOCK_KINDS, "list", "minus_metadata")
        },
        "markdown_inline_node_count": inline_count,
        "matches": records,
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
