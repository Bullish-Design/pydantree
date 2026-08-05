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
    `Pair` — the attribute's own line, not the class line. A regression
    collapsing every child site back to the class line (while keeping the
    correct file) must FAIL this test."""
    # derive the expected lines from the source itself — no hard-coded
    # fragile numbers: key/value lines are the `key: Name` / `value: Name`
    # annotation lines; the class line is the `class Pair(Rule):` line
    lines = AUTHOR_SRC.splitlines()
    key_line = next(i for i, ln in enumerate(lines, 1)
                    if ln.strip() == "key: Name")
    value_line = next(i for i, ln in enumerate(lines, 1)
                      if ln.strip() == "value: Name")
    class_line = next(i for i, ln in enumerate(lines, 1)
                      if ln.strip() == "class Pair(Rule):")
    assert len({key_line, value_line, class_line}) == 3, \
        "the fixture must put the three lines on distinct rows"

    f = tmp_path / "authorgram2.py"
    f.write_text(AUTHOR_SRC)
    mod = types.ModuleType("authorgram2")
    mod.__file__ = str(f)
    sys.modules["authorgram2"] = mod
    try:
        exec(compile(AUTHOR_SRC, str(f), "exec"), mod.__dict__)
        g = mod.assemble("g", start=mod.Pair, rules=[mod.Name, mod.Pair])
        # every body-node site must be non-null and point at the author's
        # temporary file — never into the library
        sites = [s for n in _iter_body_nodes(as_node(g.rules["pair"]))
                 if (s := site_of(n)) is not None]
        assert sites, "expected at least one body-node site"
        assert all(s.file == str(f) for s in sites)
        assert all("rules.py" not in s.file for s in sites)
        # the two attribute references carry their OWN annotation lines, and
        # the recorded source text identifies the corresponding attribute
        by_source: dict[str, RuleSite] = {}
        for s in sites:
            by_source.setdefault(s.source.strip(), s)
        key_site = by_source["key: Name"]
        value_site = by_source["value: Name"]
        assert key_site.lineno == key_line, \
            f"key site {key_site.lineno} collapsed away from line {key_line}"
        assert value_site.lineno == value_line, \
            f"value site {value_site.lineno} collapsed away from line {value_line}"
        # distinct from each other AND from the class line (the seq node's
        # coarser fallback — proving the attributes are more precise)
        assert key_site.lineno != value_site.lineno
        assert class_line not in (key_site.lineno, value_site.lineno)
    finally:
        sys.modules.pop("authorgram2", None)
