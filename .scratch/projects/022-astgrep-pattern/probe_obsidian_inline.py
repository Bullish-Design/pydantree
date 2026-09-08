"""Build and exercise the bounded Obsidian inline grammar."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pydantree_sitter as pt

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import obsidian_inline

SOURCE = (
    "[[Target|Alias]] ![[Embed.png]] #tag/nested [!note]- "
    "key:: value ^abc ==hi== %%x%%"
)
KINDS = (
    "wiki_link", "embed", "tag", "callout_marker", "inline_field",
    "block_id", "highlight", "comment",
)


def main() -> None:
    result = obsidian_inline.build()
    bundle = result.package(HERE / "evidence" / "obsidian-inline-bundle")
    language = pt.Language.load_bundle(bundle)
    language.register_astgrep(
        name="obsidian_inline", extensions=["md"],
        meta_var_char="$", expando_char="_",
    )
    found = {
        kind: [m.text for m in pt.Pattern(
            pt.Rule(kind=kind), language=language).find_all(SOURCE)]
        for kind in KINDS
    }
    tree = language.parse(SOURCE)
    child_types = [child.type for child in tree.root_node.children]
    evidence = {
        "source": SOURCE,
        "bundle": str(bundle),
        "same_artifact": pt.Pattern(
            pt.Rule(kind="wiki_link"), language=language).agreement.same_artifact,
        "matches": found,
        "child_types": child_types,
    }
    (HERE / "evidence" / "obsidian-inline.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    assert all(found.values()), found
    assert [kind for kind in child_types if kind != "text"] == list(KINDS), child_types


if __name__ == "__main__":
    main()
