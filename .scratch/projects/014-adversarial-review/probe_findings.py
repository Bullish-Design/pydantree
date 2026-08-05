"""Adversarial-review probes: verify suspected bugs with live repros."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from typing import Annotated
import tree_sitter_python
import tree_sitter_json
from pydantree_sitter import OutputModel, M, capture, NodeKind


def probe_1_cross_language_compile_cache():
    """Query.compile caches the first language; a second language reuses it."""
    print("=== probe 1: cross-language compile cache ===")

    class Assign(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: str = capture("left")

    rows = Assign.extract("X = 1", language=tree_sitter_python)
    print("  python rows:", [(r.name) for r in rows])
    try:
        rows2 = Assign.extract('{"a": 1}', language=tree_sitter_json)
        print("  json rows (should have raised QueryBuildError!):", rows2)
    except Exception as e:
        print(f"  json raised: {type(e).__name__}: {str(e)[:120]}")

    # control: a FRESH identical model compiled against json first
    class Assign2(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: str = capture("left")

    try:
        Assign2.extract('{"a": 1}', language=tree_sitter_json)
        print("  control: no error (unexpected)")
    except Exception as e:
        print(f"  control fresh model raised: {type(e).__name__} (expected)")


def probe_2_nodekind_tuple_field_mode():
    """NodeKind(('true','false')) in field mode: docstring says one pattern
    per kind; _derive_field uses kinds[0] only."""
    print("=== probe 2: NodeKind tuple alternation in field mode ===")

    class Flag(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: str = capture("left")
        value: Annotated[str, NodeKind(("true", "false"))] = capture("right")

    src = "A = True\nB = False\n"
    rows = Flag.extract(src, language=tree_sitter_python)
    print("  emitted query:\n   ", Flag.compiled_source().replace("\n", "\n    "))
    print(f"  rows: {[(r.name, r.value) for r in rows]}")
    print(f"  EXPECTED 2 rows (True+False); got {len(rows)}")


def probe_3_duplicate_results_shape():
    """field-mode list path: order bookkeeping when anchors repeat."""
    print("=== probe 3: field-mode lists basic sanity ===")

    class Call(OutputModel):
        __match__ = M("module", "expression_statement", "call")
        args: list[str] = capture("arguments")

    rows = Call.extract("f(1, 2)\ng(3)\n", language=tree_sitter_python)
    print("  rows:", [r.args for r in rows])


def probe_4_stderr_warning_noise():
    """binding warnings print to stderr on EVERY extract call."""
    print("=== probe 4: warning-noise on every extract ===")
    import io, contextlib

    class Bad(OutputModel):
        __match__ = M("module", "expression_statement", "assignment")
        name: str = capture("left")
        oops: int  # no binding, no default -> warning

    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        for _ in range(3):
            try:
                Bad.extract("X = 1", language=tree_sitter_python, strict=False)
            except Exception:
                pass
    n = buf.getvalue().count("model-warning")
    print(f"  warning printed {n} times for 3 extract calls (uses print, not warnings module)")


def probe_5_registry_leak():
    """register=True global registry: schema applies to later bare-language callers."""
    print("=== probe 5: schema registry is global mutable state ===")
    from pydantree_sitter.typed import _SCHEMA_REGISTRY
    print("  registry contents:", dict(_SCHEMA_REGISTRY))


if __name__ == "__main__":
    probe_1_cross_language_compile_cache()
    probe_2_nodekind_tuple_field_mode()
    probe_3_duplicate_results_shape()
    probe_4_stderr_warning_noise()
    probe_5_registry_leak()
