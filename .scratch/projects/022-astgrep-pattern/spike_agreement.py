"""Phase 0 — the grammar agreement spike (CONCEPT.md §13).

One question: do ast-grep's vendored Python grammar and `tree_sitter_python`
agree on node kinds and byte ranges, over real Python source?

The spike answers it in two independent measurements, because they have
different consequences:

  A. NODE-SET AGREEMENT — parse each corpus file with both engines and
     compare the full (kind, start_byte, end_byte) set. This is the §4.2
     probe, run over a corpus instead of a fixture.

  B. RESOLUTION — run representative patterns, and for every match AND every
     capture attempt the exact-range node lookup of §4.1. Whole matches and
     captures are counted SEPARATELY: whole-match ranges are the ones §10's
     `.extract()` needs, capture ranges are where grammar revisions are most
     likely to disagree, and a design that keeps one while dropping the other
     is a real outcome the binary gate would hide.

Every offset that leaves ast-grep is a CHARACTER offset (`Pos.index`), and
every offset in pydantree is a BYTE offset. `_char_to_byte` is the conversion
and it is not optional — see FINDINGS.md.

Run: devenv shell -- python .scratch/projects/022-astgrep-pattern/spike_agreement.py
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

import tree_sitter
import tree_sitter_python
from ast_grep_py import SgRoot

import ast_grep_py
from importlib.metadata import PackageNotFoundError, version as _dist_version


def dist_version(name: str) -> str:
    """The installed distribution version. Neither `ast_grep_py` nor
    `tree_sitter_python` exposes `__version__`, so read the metadata — this
    string goes into `GrammarAgreement.digest` (CONCEPT.md §4.2) and a
    literal "unknown" there would make two recorded runs incomparable."""
    try:
        return _dist_version(name)
    except PackageNotFoundError:  # pragma: no cover
        return "unknown"

HERE = pathlib.Path(__file__).parent
EVIDENCE = HERE / "evidence"
ROOT = HERE.parents[2]
CORPUS = sorted((ROOT / "src" / "pydantree_sitter").glob("*.py"))

LANG = tree_sitter.Language(tree_sitter_python.language())
PARSER = tree_sitter.Parser(LANG)


# --------------------------------------------------------------------------
# offsets

NAIVE = "--naive-offsets" in sys.argv


def char_to_byte_table(text: str) -> list[int]:
    """Map each character index -> byte index. Index N (== len) is the end.

    `--naive-offsets` returns the identity table instead, i.e. it treats
    ast-grep's character offsets AS byte offsets. That run exists to prove
    the conversion is load-bearing: the whole corpus carries non-ASCII text,
    so the naive run must fail loudly. If it ever passes, this spike is not
    measuring what it claims to measure.
    """
    if NAIVE:
        return list(range(len(text) + 1))
    table = [0] * (len(text) + 1)
    b = 0
    for i, ch in enumerate(text):
        table[i] = b
        b += len(ch.encode("utf-8"))
    table[len(text)] = b
    return table


# --------------------------------------------------------------------------
# node sets

def ts_nodes(tree: tree_sitter.Tree, named_only: bool) -> set[tuple[str, int, int]]:
    out: set[tuple[str, int, int]] = set()
    stack = [tree.root_node]
    while stack:
        n = stack.pop()
        if n.is_named or not named_only:
            out.add((n.type, n.start_byte, n.end_byte))
        stack.extend(n.children)
    return out


def sg_nodes(root, table: list[int], named_only: bool) -> set[tuple[str, int, int]]:
    out: set[tuple[str, int, int]] = set()
    stack = [root]
    while stack:
        n = stack.pop()
        if n.is_named() or not named_only:
            r = n.range()
            out.add((n.kind(), table[r.start.index], table[r.end.index]))
        stack.extend(n.children())
    return out


# --------------------------------------------------------------------------
# resolution (§4.1) — exact range, or nothing

def build_index(tree: tree_sitter.Tree) -> dict[tuple[int, int], list[str]]:
    idx: dict[tuple[int, int], list[str]] = {}
    stack = [tree.root_node]
    while stack:
        n = stack.pop()
        idx.setdefault((n.start_byte, n.end_byte), []).append(n.type)
        stack.extend(n.children)
    return idx


PATTERNS = [
    "def $NAME($$$ARGS): $$$BODY",
    "class $NAME: $$$BODY",
    "class $NAME($$$BASES): $$$BODY",
    "return $VAL",
    "raise $EXC($$$ARGS)",
    "if $COND: $$$BODY",
    "for $VAR in $ITER: $$$BODY",
    "while $COND: $$$BODY",
    "with $CTX as $VAR: $$$BODY",
    "$OBJ.$METHOD($$$ARGS)",
    "$A = $B",
    "$A: $T = $B",
    "import $MOD",
    "from $MOD import $$$NAMES",
    "assert $COND",
    "try: $$$BODY except $EXC: $$$HANDLER",
    "lambda $$$ARGS: $BODY",
    "[$X for $Y in $Z]",
    "{$K: $V}",
    "$F($$$ARGS)",
    "not $X",
    "$A if $C else $B",
    "yield $V",
    "@$DEC",
]

MULTI = "$$$"


def main() -> int:
    EVIDENCE.mkdir(exist_ok=True)

    files = 0
    lines = 0
    nonascii_files = 0
    named = {"total": 0, "exact": 0, "only_sg": Counter(), "only_ts": Counter(), "files": []}
    anon = {"total": 0, "exact": 0, "only_sg": Counter(), "only_ts": Counter(), "files": []}
    node_exact = node_total = 0
    only_sg: Counter[str] = Counter()
    only_ts: Counter[str] = Counter()
    range_mismatch_files: list[str] = []

    m_total = m_ok = 0
    c_total = c_ok = 0
    m_fail: Counter[str] = Counter()
    c_fail: Counter[str] = Counter()
    kind_disagree: Counter[tuple[str, str]] = Counter()
    per_pattern: dict[str, dict] = {p: {"matches": 0, "m_ok": 0, "caps": 0, "c_ok": 0} for p in PATTERNS}

    for path in CORPUS:
        text = path.read_text(encoding="utf-8")
        data = text.encode("utf-8")
        files += 1
        lines += text.count("\n")
        nonascii_files += 0 if text.isascii() else 1
        table = char_to_byte_table(text)

        tree = PARSER.parse(data)
        sg = SgRoot(text, "python").root()

        for named_only, bucket in ((True, named), (False, anon)):
            a = sg_nodes(sg, table, named_only=named_only)
            b = ts_nodes(tree, named_only=named_only)
            bucket["total"] += len(b)
            bucket["exact"] += len(a & b)
            for kind, _s, _e in a - b:
                bucket["only_sg"][kind] += 1
            for kind, _s, _e in b - a:
                bucket["only_ts"][kind] += 1
            if a != b and path.name not in bucket["files"]:
                bucket["files"].append(path.name)
        node_total = named["total"]
        node_exact = named["exact"]
        only_sg = named["only_sg"]
        only_ts = named["only_ts"]
        range_mismatch_files = named["files"]

        idx = build_index(tree)

        for pat in PATTERNS:
            stats = per_pattern[pat]
            for node in sg.find_all(pattern=pat):
                r = node.range()
                key = (table[r.start.index], table[r.end.index])
                m_total += 1
                stats["matches"] += 1
                hit = idx.get(key)
                if hit is None:
                    m_fail[pat] += 1
                else:
                    m_ok += 1
                    stats["m_ok"] += 1
                    if node.kind() not in hit:
                        kind_disagree[(node.kind(), hit[0])] += 1

                for mv in metavars(pat):
                    if mv.startswith(MULTI):
                        caps = node.get_multiple_matches(mv[len(MULTI):])
                    else:
                        got = node.get_match(mv[1:])
                        caps = [got] if got is not None else []
                    for c in caps:
                        cr = c.range()
                        ckey = (table[cr.start.index], table[cr.end.index])
                        c_total += 1
                        stats["caps"] += 1
                        if ckey in idx:
                            c_ok += 1
                            stats["c_ok"] += 1
                        else:
                            c_fail[f"{pat} :: {mv}"] += 1

    report = {
        "astgrep_py_version": dist_version("ast-grep-py"),
        "tree_sitter_python_version": dist_version("tree-sitter-python"),
        "tree_sitter_version": tree_sitter.__version__,
        "offset_mode": "naive (char offsets used AS byte offsets)" if NAIVE else "char->byte converted",
        "corpus": {"files": files, "lines": lines, "files_with_non_ascii": nonascii_files},
        "node_set_named": _bucket(named),
        "node_set_all_incl_anonymous": _bucket(anon),
        "resolution": {
            "whole_match": {
                "total": m_total,
                "resolved": m_ok,
                "failure_rate": round(1 - m_ok / m_total, 6) if m_total else None,
                "failures_by_pattern": dict(m_fail.most_common(20)),
            },
            "capture": {
                "total": c_total,
                "resolved": c_ok,
                "failure_rate": round(1 - c_ok / c_total, 6) if c_total else None,
                "failures_by_pattern_metavar": dict(c_fail.most_common(20)),
            },
            "kind_disagreements": {f"{k[0]}|{k[1]}": v for k, v in kind_disagree.most_common(20)},
        },
        "per_pattern": per_pattern,
    }

    out = EVIDENCE / ("agreement-naive.json" if NAIVE else "agreement.json")
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "per_pattern"}, indent=2))
    print(f"\nwrote {out}")
    return 0


def _bucket(b: dict) -> dict:
    return {
        "pydantree_nodes": b["total"],
        "exact_matches": b["exact"],
        "rate": round(b["exact"] / b["total"], 6) if b["total"] else None,
        "only_astgrep_kinds": dict(b["only_sg"].most_common(20)),
        "only_pydantree_kinds": dict(b["only_ts"].most_common(20)),
        "files_with_any_mismatch": b["files"],
    }


def metavars(pattern: str) -> list[str]:
    """The `$NAME` / `$$$NAME` tokens in a pattern, in order, deduplicated."""
    out: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        if pattern[i] != "$":
            i += 1
            continue
        j = i
        while j < n and pattern[j] == "$":
            j += 1
        dollars = j - i
        k = j
        while k < n and (pattern[k].isalnum() or pattern[k] == "_"):
            k += 1
        name = pattern[j:k]
        if name and name.isupper():
            tok = ("$$$" if dollars >= 3 else "$") + name
            if tok not in out:
                out.append(tok)
        i = max(k, i + 1)
    return out


if __name__ == "__main__":
    sys.exit(main())
