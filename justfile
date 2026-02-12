set shell := ["bash", "-cu"]

codegen-ingest LANGUAGE="python" QUERY_PACK="minimal_pack":
	PYTHONPATH=src python -m pydantree.codegen.cli ingest {{LANGUAGE}} {{QUERY_PACK}}

codegen-normalize LANGUAGE="python" QUERY_PACK="minimal_pack":
	PYTHONPATH=src python -m pydantree.codegen.cli normalize {{LANGUAGE}} {{QUERY_PACK}}

codegen-emit LANGUAGE="python" QUERY_PACK="minimal_pack":
	PYTHONPATH=src python -m pydantree.codegen.cli emit {{LANGUAGE}} {{QUERY_PACK}}

codegen-manifest LANGUAGE="python" QUERY_PACK="minimal_pack":
	PYTHONPATH=src python -m pydantree.codegen.cli manifest {{LANGUAGE}} {{QUERY_PACK}}

codegen-pipeline LANGUAGE="python" QUERY_PACK="minimal_pack":
	just codegen-ingest LANGUAGE={{LANGUAGE}} QUERY_PACK={{QUERY_PACK}}
	just codegen-normalize LANGUAGE={{LANGUAGE}} QUERY_PACK={{QUERY_PACK}}
	just codegen-emit LANGUAGE={{LANGUAGE}} QUERY_PACK={{QUERY_PACK}}
	just codegen-manifest LANGUAGE={{LANGUAGE}} QUERY_PACK={{QUERY_PACK}}
