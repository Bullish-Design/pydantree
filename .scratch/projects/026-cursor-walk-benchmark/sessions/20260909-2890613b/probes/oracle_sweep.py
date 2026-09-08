"""Exhaustive differential oracle: query vs recursive walk vs cursor walk.

For every kind in every generated namespace, over every real corpus file,
run the three anchor strategies and compare the anchor sequence and the
resolved typed rows. The sweep is the correctness half of the decision gate.

Output: JSON on stdout, human summary on stderr.
"""

from __future__ import annotations

import json
import sys
import traceback

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

import harness  # noqa: E402

LANGUAGES = ("python", "bash", "nix", "rust", "markdown")
TIERS = ("small", "medium", "large")
ROW_TIERS = ("small", "medium")


def spans(nodes):
    return [[n.start_byte, n.end_byte] for n in nodes]


def summarize(value):
    """A comparable, JSON-safe summary of one resolved field value."""
    from pydantree_sitter import Node

    if isinstance(value, Node):
        return {"__node__": [value.span.start_byte, value.span.end_byte]}
    if isinstance(value, list):
        return [summarize(item) for item in value]
    if isinstance(value, dict):
        return {str(k): summarize(v) for k, v in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def row_summary(rows):
    out = []
    for row in rows:
        fields = {name: summarize(getattr(row, name, None))
                  for name in type(row).model_fields}
        out.append({"span": [row.span.start_byte, row.span.end_byte],
                    "fields": fields})
    return out


def run() -> dict:
    report = {"languages": {}, "disagreements": [], "errors": []}
    for language in LANGUAGES:
        grammar = harness.grammar(language)
        namespace = grammar.nodes
        kinds = sorted(
            name for name, value in vars(namespace).items()
            if isinstance(value, type) and hasattr(value, "__kind__"))
        trees = {}
        for cf in harness.corpus_files():
            if cf.language != language:
                continue
            trees[cf.tier] = (cf, grammar.parse(cf.text))
        lang_report = {"kinds": len(kinds), "cases": 0, "agree": 0,
                       "query_build_fallback": [], "tiers": {}}
        for tier in TIERS:
            if tier not in trees:
                continue
            cf, tree = trees[tier]
            raw = tree.root_node
            tier_report = {"file": str(cf.path), "sha256": cf.sha256,
                           "bytes": cf.bytes,
                           "nodes": raw.descendant_count,
                           "kinds_with_matches": 0, "anchor_mismatch": 0,
                           "row_mismatch": 0}
            for kind_name in kinds:
                cls = getattr(namespace, kind_name)
                try:
                    a_query, fell_back = harness.anchors_query(
                        raw, cls, grammar.language)
                    a_rec = harness.anchors_recwalk(raw, cls)
                    a_cur = harness.anchors_cursor(raw, cls, grammar.language)
                except Exception:
                    report["errors"].append({
                        "language": language, "tier": tier, "kind": kind_name,
                        "where": "anchors",
                        "traceback": traceback.format_exc().splitlines()[-3:]})
                    continue
                if fell_back and kind_name not in \
                        lang_report["query_build_fallback"]:
                    lang_report["query_build_fallback"].append(kind_name)
                lang_report["cases"] += 1
                s_query, s_rec, s_cur = (spans(a_query), spans(a_rec),
                                         spans(a_cur))
                if s_rec:
                    tier_report["kinds_with_matches"] += 1
                agree = (s_rec == s_cur)
                if not agree:
                    tier_report["anchor_mismatch"] += 1
                    report["disagreements"].append({
                        "language": language, "tier": tier, "kind": kind_name,
                        "axis": "cursor_vs_recwalk",
                        "recwalk": len(s_rec), "cursor": len(s_cur),
                        "sample_rec": s_rec[:3], "sample_cur": s_cur[:3]})
                if s_query != s_rec:
                    report["disagreements"].append({
                        "language": language, "tier": tier, "kind": kind_name,
                        "axis": "query_vs_recwalk",
                        "query": len(s_query), "recwalk": len(s_rec),
                        "query_fell_back": fell_back,
                        "only_in_recwalk": [s for s in s_rec
                                            if s not in s_query][:3],
                        "only_in_query": [s for s in s_query
                                          if s not in s_rec][:3],
                        "order_only": sorted(s_query) == sorted(s_rec)})
                else:
                    lang_report["agree"] += 1
                if tier in ROW_TIERS:
                    try:
                        r_rec, f_rec = harness.rows_from(a_rec, cls)
                        r_cur, f_cur = harness.rows_from(a_cur, cls)
                        if row_summary(r_rec) != row_summary(r_cur) or \
                                f_rec != f_cur:
                            tier_report["row_mismatch"] += 1
                            report["disagreements"].append({
                                "language": language, "tier": tier,
                                "kind": kind_name, "axis": "rows"})
                    except Exception:
                        report["errors"].append({
                            "language": language, "tier": tier,
                            "kind": kind_name, "where": "rows",
                            "traceback":
                                traceback.format_exc().splitlines()[-3:]})
            lang_report["tiers"][tier] = tier_report
        report["languages"][language] = lang_report
    return report


if __name__ == "__main__":
    result = run()
    for language, lang in result["languages"].items():
        print(f"{language:9s} kinds={lang['kinds']:4d} cases={lang['cases']:5d} "
              f"query==recwalk={lang['agree']:5d} "
              f"querybuild_fallback_kinds={len(lang['query_build_fallback'])}",
              file=sys.stderr)
        for tier, t in lang["tiers"].items():
            print(f"    {tier:6s} {t['bytes']:8d}B nodes={t['nodes']:7d} "
                  f"kinds_with_matches={t['kinds_with_matches']:4d} "
                  f"cursor_vs_recwalk_mismatch={t['anchor_mismatch']} "
                  f"row_mismatch={t['row_mismatch']}", file=sys.stderr)
    print(f"disagreements={len(result['disagreements'])} "
          f"errors={len(result['errors'])}", file=sys.stderr)
    json.dump(result, sys.stdout, indent=1)
