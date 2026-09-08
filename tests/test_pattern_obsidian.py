"""Project 022 Obsidian inline grammar integration."""

import subprocess
import sys
from pathlib import Path

import pytest

BUNDLE = (Path(__file__).parents[1] / ".scratch" / "projects" /
          "022-astgrep-pattern" / "evidence" / "obsidian-inline-bundle")


def test_scoped_inline_search_finds_obsidian_constructs():
    """Run dynamic registration in a fresh process.

    ast-grep-py accepts all dynamic languages only in its first registration
    call. The repository also tests a JSON dynamic language, so this test
    must not depend on collection order.
    """
    if not BUNDLE.exists():
        pytest.skip("project 022 inline bundle is not built")
    code = """
import os
from pydantree_sitter import Language, Pattern, Rule
language = Language.load_bundle(os.environ["BUNDLE"])
language.register_astgrep(
    name="obsidian_inline_test", extensions=["md"],
    meta_var_char="$", expando_char="_",
)
source = "[[Target]] text #tag ==mark== %%note%%"
root = language.parse(source).root_node
expected = {
    "wiki_link": "[[Target]]", "tag": "#tag",
    "highlight": "==mark==", "comment": "%%note%%",
}
for kind, text in expected.items():
    pattern = Pattern(Rule(kind=kind), language=language)
    matches = pattern.find_all_in(root, source)
    assert [match.text for match in matches] == [text]
    assert matches[0].span.start_byte == source.encode().index(text.encode())
    assert matches[0].agreement == pattern.agreement.digest
    """
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, check=False,
        env={**__import__("os").environ, "BUNDLE": str(BUNDLE)},
    )
    assert result.returncode == 0, result.stderr


def test_markdown_blocks_drive_rebased_inline_search():
    """Use ast-grep Markdown inline spans as fragment-parser inputs."""
    if not BUNDLE.exists():
        pytest.skip("project 022 inline bundle is not built")
    code = """
from ast_grep_py import SgRoot
from pydantree_sitter import Language, Pattern, Rule
from pydantree_sitter.agreement import char_to_byte_table

language = Language.load_bundle(__import__("os").environ["BUNDLE"])
language.register_astgrep(
    name="obsidian_inline_markdown_test", extensions=["md"],
    meta_var_char="$", expando_char="_",
)
source = (
    "---\\n"
    "tags: [project]\\n"
    "---\\n\\n"
    "# Café [[Target#Heading]]\\n\\n"
    "Paragraph pré [[Target]] [[Target|Alias]] [[Target#^block]]\\n"
    "with ![[Embed.png]] #tag #nested/tag key:: value ==highlight==\\n"
    "%%comment%% ^abc123 and [[Café]] inside.\\n\\n"
    "> [!note] Callout [[Quoted]]\\n"
    "> Body pré ^quoteid.\\n"
    ">\\n"
    "> [!warning]- Warning [[Warned]]\\n\\n"
    "- [ ] tâche [[Task]]\\n"
    "- [x] done #checked\\n"
)
block_kinds = {
    "atx_heading", "paragraph", "list_item", "block_quote",
    "task_list_marker_checked", "task_list_marker_unchecked",
}
table = char_to_byte_table(source)
data = source.encode("utf-8")
patterns = {kind: Pattern(Rule(kind=kind), language=language)
            for kind in (
                "wiki_link", "embed", "tag", "callout_marker",
                "inline_field", "block_id", "highlight", "comment",
            )}
rows = []

def walk(node, ancestors=()):
    path = ancestors + ((node.kind(),) if node.kind() in block_kinds else ())
    if node.kind() == "inline":
        point = node.range()
        start_char = point.start.index
        end_char = point.end.index
        fragment = source[start_char:end_char]
        base_byte = table[start_char]
        for kind, pattern in patterns.items():
            for match in pattern.find_all_rebased(
                    fragment, base_byte=base_byte):
                original = data[match.span.start_byte:match.span.end_byte].decode()
                assert original == match.text
                assert base_byte <= match.span.start_byte
                assert match.span.end_byte <= table[end_char]
                rows.append((kind, match.text.strip(), path,
                             match.span.start_byte, match.span.end_byte))
    for child in node.children():
        walk(child, path)

root = SgRoot(source, "markdown").root()
walk(root)
assert len(root.find_all(kind="task_list_marker_unchecked")) == 1
assert len(root.find_all(kind="task_list_marker_checked")) == 1
expected = {
    "wiki_link": {
        "[[Target#Heading]]", "[[Target]]", "[[Target|Alias]]",
        "[[Target#^block]]", "[[Café]]", "[[Quoted]]", "[[Warned]]",
        "[[Task]]",
    },
    "embed": {"![[Embed.png]]"},
    "tag": {"#tag", "#nested/tag", "#checked"},
    "callout_marker": {"[!note]", "[!warning]-"},
    "inline_field": {"key:: value"},
    "block_id": {"^abc123", "^quoteid"},
    "highlight": {"==highlight=="},
    "comment": {"%%comment%%"},
}
seen = {kind: set() for kind in expected}
for kind, text, path, start, end in rows:
    seen[kind].add(text)
    if text == "[[Target#Heading]]":
        assert path == ("atx_heading",)
    if text == "[[Task]]":
        assert path == ("list_item", "paragraph")
    if text in {"[!note]", "[!warning]-"}:
        assert path[:2] == ("block_quote", "paragraph")
assert seen == expected
assert {path[:1] for _, _, path, _, _ in rows} >= {
    ("atx_heading",), ("paragraph",), ("block_quote",), ("list_item",),
}
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, check=False,
        env={**__import__("os").environ, "BUNDLE": str(BUNDLE)},
    )
    assert result.returncode == 0, result.stderr
