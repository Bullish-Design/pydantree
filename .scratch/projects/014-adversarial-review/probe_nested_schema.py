"""Probe 6: nested record OutputModel under a SCHEMA-BOUND extraction.

Suspicion: _record_kwargs() recurses with the nested model's schema-LESS
_derived_cache (whose inner query has no @__anchor__ capture) while passing
the outer record_kind — so `if not anc or anc[0].id != rec.id: continue`
drops every nested match, and nested fields never materialize.
"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / ".scratch" / "projects" / "006-tsquery-bridge"))

import tree_sitter_json
from tscore.schema import NodeSchema, derive_from_ir
from tsquery import OutputModel, M, Language

from json_grammar import build as build_json

schema = NodeSchema.from_list(derive_from_ir(build_json().build()), name="json")

SRC = '''[
  {"name": "ada", "address": {"city": "london"}},
  {"name": "bob", "address": {"city": "paris"}}
]'''


class Address(OutputModel):
    __match__ = M("document", "object", record=True)
    city: str


class Person(OutputModel):
    __match__ = M("document", "array", "object", record=True)
    name: str
    address: Address


print("--- schema-less (Phase-1 path) ---")
rows = Person.extract(SRC, language=tree_sitter_json)
print("rows:", [(r.name, r.address.city) for r in rows])

print("--- schema-bound (Phase-4 path) ---")
lang = Language.load(tree_sitter_json.language(), schema=schema)
try:
    rows = Person.extract(SRC, language=lang)
    print("rows:", [(r.name, r.address.city if r.address else None) for r in rows])
except Exception as e:
    print(f"RAISED {type(e).__name__}:")
    print("  ", str(e)[:400])
