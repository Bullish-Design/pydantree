`test_binding_wheel.py` — deleted Product A binding/materializer coverage; typed `Grammar.parse().find()` owns parsing and node construction.
`test_codegen.py` — merged into `test_generate.py`; the generator now has one typed-node implementation.
`test_extract.py` — deleted legacy OutputModel/extractor matrix; typed node annotations and `Grammar.find()` replace the extraction pipeline.
`test_tsquery_port.py` — deleted legacy query compiler coverage; typed traversal is covered by `test_grammar_nodes.py` and `test_bundle.py`.
`test_tsquery_schema.py` — deleted legacy schema-job binding coverage; `NodeMeta` validates annotations against `NodeSchema` at class creation.
`test_valuemap_check.py` — merged into `test_codecs.py`; codecs are class methods and there is no runtime value map.
`test_raw_query.py` — split into `test_raw.py`; raw query behavior remains, while extractor bind-path assertions are impossible after the surface deletion.
`test_pattern_agreement.py` — deleted ast-grep/Product A language-wrapper integration; the typed core has no `Language` wrapper and pattern agreement remains a deferred subsystem.
`test_pattern_dynamic.py` — deleted dynamic ast-grep binding integration; bundle consumers use the typed node universe directly.
`test_pattern_module.py` — deleted wrapper-bound pattern integration; pure pattern rule construction remains in `test_pattern_rules.py`.
`test_pattern_obsidian.py` — deleted historical ast-grep example integration; it depended on the removed wrapper and an untracked scratch bundle.
`test_pattern_roundtrip.py` — deleted wrapper-bound ast-grep rewrite integration; rewrite mechanics are outside this typed-node refactor.
`test_oracles.py` — deleted legacy example extraction harness; examples are being migrated to typed traversal rather than preserving the removed extractor API.
`test_checks_nullable.py` — merged into `test_checks.py`; nullable analysis remains covered in the consolidated checks suite.
`test_phase6_fixes.py` — merged into `test_rules.py`; Product B rule-surface regressions remain covered in the consolidated rules suite.
