set shell := ["bash", "-cu"]

codegen-ingest ROOT="tests/data":
	PYTHONPATH=src python -m pydantree.codegen.cli ingest {{ROOT}} --out build/ingest.json

codegen-normalize:
	PYTHONPATH=src python -m pydantree.codegen.cli normalize --input build/ingest.json --out build/normalize.json

codegen-emit:
	PYTHONPATH=src python -m pydantree.codegen.cli emit --input build/normalize.json --output-dir build/generated --out build/emit.json

codegen-manifest:
	PYTHONPATH=src python -m pydantree.codegen.cli manifest --ingest build/ingest.json --normalize build/normalize.json --emit build/emit.json --out build/manifest.json

codegen-pipeline ROOT="tests/data":
	just codegen-ingest ROOT={{ROOT}}
	just codegen-normalize
	just codegen-emit
	just codegen-manifest
