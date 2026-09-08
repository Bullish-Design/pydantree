"""Quantify the retained path's own headroom: cache the compiled query.

The shipped ``find_in`` builds and compiles a fresh ``Query`` on every call,
and re-pays a failed compile for every kind whose emitted query the parser
rejects. This probe measures a per-(class, language) compile cache while
keeping the query path's semantics byte-for-byte, and checks that the rows
are identical.
"""

from __future__ import annotations

import gc
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness  # noqa: E402
from bench import REPEATS, SUBJECTS, stats  # noqa: E402
from oracle_sweep import row_summary  # noqa: E402

from pydantree_sitter.errors import ExtractionError, QueryBuildError  # noqa: E402
from pydantree_sitter.find import _walk, find_in, query_source  # noqa: E402
from pydantree_sitter.match import match_ancestor_path  # noqa: E402
from pydantree_sitter.nodes import _MatchRejected, normalize_under  # noqa: E402
from pydantree_sitter.raw import Cursor, Query  # noqa: E402

_CACHE: dict[tuple[int, int], object] = {}
_UNCOMPILABLE = object()


def _cached_query(cls, language):
    key = (id(cls), id(language))
    hit = _CACHE.get(key)
    if hit is None:
        try:
            hit = Query.raw(query_source(cls)).compile(language)
        except QueryBuildError:
            hit = _UNCOMPILABLE
        _CACHE[key] = hit
    return hit


def find_in_cached(raw, cls, language):
    """``find_in``'s query path with the compile hoisted into a cache."""
    if getattr(cls, "__raw_query__", None) is not None:
        return find_in(raw, cls, language)
    out: list = []
    failures: list = []
    compiled = _cached_query(cls, language)
    if compiled is _UNCOMPILABLE:
        _walk(raw, cls, out, failures)
    else:
        under = tuple(getattr(cls, "__under__", None) or ())
        path = normalize_under((*under, cls))
        seen: set[tuple[int, int]] = set()
        for match in Cursor(compiled, raw).matches_on(raw):
            for anchor in match.nodes("__anchor"):
                key = (anchor.start_byte, anchor.end_byte)
                if key in seen or not match_ancestor_path(anchor, path):
                    continue
                seen.add(key)
                try:
                    out.append(cls.from_node(anchor))
                except _MatchRejected:
                    pass
                except Exception as error:  # noqa: BLE001
                    failures.append(error)
    if failures:
        raise ExtractionError([], cls)
    return out


def timed(fn, repeats):
    fn()
    samples = []
    for _ in range(repeats):
        gc.collect()
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return stats(samples)


def outcome(fn):
    try:
        return {"rows": row_summary(fn())}
    except Exception as error:  # noqa: BLE001
        return {"error": type(error).__name__}


def run():
    out = []
    for language, names in SUBJECTS.items():
        grammar = harness.grammar(language)
        ts = grammar.language
        for cf in harness.corpus_files():
            if cf.language != language or cf.tier == "small":
                continue
            raw = grammar.parse(cf.text).root_node
            for name in names:
                cls = getattr(grammar.nodes, name, None)
                if cls is None:
                    continue
                same = outcome(lambda: find_in(raw, cls, ts)) == \
                    outcome(lambda: find_in_cached(raw, cls, ts))
                reps = REPEATS[cf.tier]
                shipped = timed(lambda: _safe(find_in, raw, cls, ts), reps)
                cached = timed(lambda: _safe(find_in_cached, raw, cls, ts),
                               reps)
                out.append({
                    "language": language, "tier": cf.tier, "class": name,
                    "rows_identical": same,
                    "shipped": shipped, "cached": cached,
                    "speedup": round(shipped["median_ms"] /
                                     max(cached["median_ms"], 1e-9), 3)})
    return out


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception:  # noqa: BLE001
        return None


if __name__ == "__main__":
    result = run()
    bad = [e for e in result if not e["rows_identical"]]
    print(f"{'lang':9s} {'tier':6s} {'class':18s} {'shipped_ms':>10s} "
          f"{'cached_ms':>10s} {'speedup':>8s} identical", file=sys.stderr)
    for e in result:
        print(f"{e['language']:9s} {e['tier']:6s} {e['class']:18s} "
              f"{e['shipped']['median_ms']:10.3f} "
              f"{e['cached']['median_ms']:10.3f} {e['speedup']:8.2f} "
              f"{e['rows_identical']}", file=sys.stderr)
    sp = [e["speedup"] for e in result]
    print(f"\nspeedup median={statistics.median(sp):.2f} min={min(sp):.2f} "
          f"max={max(sp):.2f}; rows_differ={len(bad)}", file=sys.stderr)
    json.dump(result, sys.stdout, indent=1)
