"""B10 (REVIEW 018): rule-class body nodes must carry the AUTHOR's source
site, not a site inside the library (rules.py). The advertised
finer-grained conflict sites (`Pair.value`) were inert — every combinator
node already carried a rules.py site from _track, so _stamp's
`if site_of(n) is None` gate never repointed them."""

import sys
import types

from pydantree_sitter_grammar.builder import _iter_body_nodes, as_node, site_of

AUTHOR_SRC = '''
from pydantree_sitter_grammar import Rule, assemble
class Name(Rule):
    __pattern__ = r"[a-z]+"
class Pair(Rule):
    key: Name
    value: Name
'''


def test_rule_class_nodes_point_at_author_file(tmp_path):
    f = tmp_path / "authorgram.py"
    f.write_text(AUTHOR_SRC)
    mod = types.ModuleType("authorgram")
    mod.__file__ = str(f)
    sys.modules["authorgram"] = mod
    try:
        exec(compile(AUTHOR_SRC, str(f), "exec"), mod.__dict__)
        g = mod.assemble("g", start=mod.Pair, rules=[mod.Name, mod.Pair])
        files = {site_of(n).file for n in _iter_body_nodes(as_node(g.rules["pair"]))
                 if site_of(n) is not None}
        assert files == {str(f)}, f"sites leaked into internals: {files}"
    finally:
        sys.modules.pop("authorgram", None)


def test_attribute_sites_are_more_precise_than_the_class_line(tmp_path):
    """The headline claim: conflict sites name `Pair.value`, not just
    `Pair` — the attribute's own line, not the class line."""
    f = tmp_path / "authorgram2.py"
    f.write_text(AUTHOR_SRC)
    mod = types.ModuleType("authorgram2")
    mod.__file__ = str(f)
    sys.modules["authorgram2"] = mod
    try:
        exec(compile(AUTHOR_SRC, str(f), "exec"), mod.__dict__)
        g = mod.assemble("g", start=mod.Pair, rules=[mod.Name, mod.Pair])
        # both attributes compile to tg.ref("name") leaves; their nodes must
        # carry the author file AND not the library file
        for n in _iter_body_nodes(as_node(g.rules["pair"])):
            s = site_of(n)
            assert s is not None and s.file == str(f)
            assert "rules.py" not in s.file
    finally:
        sys.modules.pop("authorgram2", None)
