# Deleted tests

- `test_generated_query_compiles_once_per_class_and_language` — the generated query construction no longer exists; `Selector` is evaluated directly by the finder.
- `test_failed_generated_query_compiles_once_and_keeps_walk_fallback` — the generated query fallback construction no longer exists; `Selector` is evaluated directly by the finder.
- `test_query_source_uses_schema_kinds_and_predicates` — `Grammar.query_source` and the generated query renderer were removed; selector data and the corpus-wide selector property test cover the matching contract.
