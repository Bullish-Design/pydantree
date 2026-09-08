"""Benchmark: recursive anchors, cursor anchors, and lazy row materialization.

Measures, on real repository corpora:
  parse cost; anchor discovery; lazy typed-row resolution; the cost of forcing
  every nested field; repeated queries over one parsed tree; broad and nested
  match shapes; peak allocation; and the run-to-run spread.

Output: JSON on stdout, human table on stderr.
"""

from __future__ import annotations

import gc
import json
import os
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness  # noqa: E402

# Representative classes per language: a broad leaf kind, a self-nesting
# kind, and a structured kind.
SUBJECTS = {
    "python": ["Identifier", "FunctionDefinition", "ClassDefinition",
                "Assignment", "String"],
    "bash": ["Command", "VariableAssignment", "BinaryExpression",
             "FunctionDefinition"],
    "nix": ["Binding", "ApplyExpression", "SelectExpression", "IfExpression"],
    "rust": ["Identifier", "ScopedIdentifier", "FunctionItem",
             "LetDeclaration", "CallExpression"],
    "markdown": ["AtxHeading", "ListItem", "FencedCodeBlock", "Section"],
}

REPEATS = {"small": 30, "medium": 15, "large": 7}


def stats(samples):
    samples = sorted(samples)
    return {
        "n": len(samples),
        "min_ms": round(samples[0] * 1e3, 4),
        "median_ms": round(statistics.median(samples) * 1e3, 4),
        "mean_ms": round(statistics.fmean(samples) * 1e3, 4),
        "p90_ms": round(samples[min(len(samples) - 1,
                                    int(0.9 * len(samples)))] * 1e3, 4),
        "max_ms": round(samples[-1] * 1e3, 4),
        "stdev_ms": round(statistics.stdev(samples) * 1e3, 4)
        if len(samples) > 1 else 0.0,
    }


def timed(fn, repeats):
    fn()  # warm the interpreter
    samples = []
    for _ in range(repeats):
        gc.collect()
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return stats(samples)


def peak_kib(fn):
    gc.collect()
    tracemalloc.start()
    fn()
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return round(peak / 1024, 1)


def materialize(value):
    """Read every nested Node field in a value tree."""
    from pydantree_sitter.nodes import Node

    if isinstance(value, Node):
        for name in type(value).model_fields:
            materialize(getattr(value, name, None))
    elif isinstance(value, (list, tuple)):
        for item in value:
            materialize(item)
    elif isinstance(value, dict):
        for item in value.values():
            materialize(item)


def find_in_fully_materialized(raw, cls, language):
    """Run the lazy path, then force the complete returned value tree."""
    from pydantree_sitter.find import find_in

    rows = find_in(raw, cls, language)
    for row in rows:
        materialize(row)
    return rows


def subjects():
    """Return all subjects, or one ``language:Class`` selection."""
    selection = os.environ.get("PDT_BENCH_ONLY")
    if not selection:
        return SUBJECTS
    language, name = selection.split(":", 1)
    return {language: [name]}


def run() -> dict:
    from pydantree_sitter.find import find_in

    report = {"environment": {}, "parse": [], "anchors": [], "rows": [],
              "repeat_scaling": [], "memory": []}
    for language, names in subjects().items():
        grammar = harness.grammar(language)
        ts_language = grammar.language
        for cf in harness.corpus_files():
            if cf.language != language:
                continue
            repeats = REPEATS[cf.tier]
            text = cf.text
            parse_stats = timed(lambda: grammar.parse(text), repeats)
            tree = grammar.parse(text)
            raw = tree.root_node
            report["parse"].append({
                "language": language, "tier": cf.tier, "bytes": cf.bytes,
                "nodes": raw.descendant_count, **parse_stats})
            for name in names:
                cls = getattr(grammar.nodes, name, None)
                if cls is None:
                    continue
                n_walk = len(harness.anchors_recwalk(raw, cls))
                base = {"language": language, "tier": cf.tier,
                        "bytes": cf.bytes, "kind": cls.__kind__,
                        "class": name, "matches": n_walk}

                entry = dict(base)
                entry["recwalk"] = timed(
                    lambda: harness.anchors_recwalk(raw, cls), repeats)
                entry["cursor"] = timed(
                    lambda: harness.anchors_cursor(raw, cls, ts_language),
                    repeats)
                report["anchors"].append(entry)

                row_entry = dict(base)
                row_entry["find_in_lazy"] = timed(
                    lambda: _safe(find_in, raw, cls, ts_language), repeats)
                row_entry["fully_materialized"] = timed(
                    lambda: _safe(find_in_fully_materialized, raw, cls,
                                  ts_language), repeats)
                row_entry["cursor_rows"] = timed(
                    lambda: _safe(harness.find_in_cursor, raw, cls,
                                  ts_language), repeats)
                report["rows"].append(row_entry)

                if cf.tier == "medium":
                    report["memory"].append({
                        **base,
                        "recwalk_peak_kib": peak_kib(
                            lambda: harness.anchors_recwalk(raw, cls)),
                        "cursor_peak_kib": peak_kib(
                            lambda: harness.anchors_cursor(raw, cls,
                                                           ts_language)),
                        "find_in_lazy_peak_kib": peak_kib(
                            lambda: _safe(find_in, raw, cls, ts_language)),
                        "fully_materialized_peak_kib": peak_kib(
                            lambda: _safe(find_in_fully_materialized, raw, cls,
                                          ts_language)),
                        "cursor_rows_peak_kib": peak_kib(
                            lambda: _safe(harness.find_in_cursor, raw, cls,
                                          ts_language)),
                    })

            # repeated anchor scans against one parsed tree (N in one pass)
            if cf.tier in ("medium", "large"):
                classes = [getattr(grammar.nodes, n) for n in names
                           if hasattr(grammar.nodes, n)]
                for count in (1, 10, 50):
                    def many_walk(count=count, classes=classes):
                        for _ in range(count):
                            for cls in classes:
                                harness.anchors_recwalk(raw, cls)

                    def many_cursor(count=count, classes=classes):
                        for _ in range(count):
                            for cls in classes:
                                harness.anchors_cursor(raw, cls, ts_language)
                    reps = 5 if count < 50 else 3
                    report["repeat_scaling"].append({
                        "language": language, "tier": cf.tier,
                        "classes": len(classes), "rounds": count,
                        "recwalk": timed(many_walk, reps),
                        "cursor": timed(many_cursor, reps)})
    return report


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception:  # noqa: BLE001 - timing must survive ExtractionError
        return None


if __name__ == "__main__":
    result = run()
    print(f"{'lang':9s} {'tier':6s} {'class':18s} {'n':>6s} "
          f"{'walk':>9s} {'cur':>9s}",
          file=sys.stderr)
    for e in result["anchors"]:
        print(f"{e['language']:9s} {e['tier']:6s} {e['class']:18s} "
              f"{e['matches']:6d} {e['recwalk']['median_ms']:9.3f} "
              f"{e['cursor']['median_ms']:9.3f}", file=sys.stderr)
    print("\nrow materialization", file=sys.stderr)
    for e in result["rows"]:
        lazy = e["find_in_lazy"]["median_ms"]
        full = e["fully_materialized"]["median_ms"]
        print(f"{e['language']:9s} {e['tier']:6s} {e['class']:18s} "
              f"{e['matches']:6d} {lazy:9.3f} {full:9.3f} "
              f"full/lazy={full / max(lazy, 1e-9):6.2f}", file=sys.stderr)
    json.dump(result, sys.stdout, indent=1)
