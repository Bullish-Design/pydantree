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
  
  
# Resolve paths from repository root and never from caller-provided raw paths.
repo_root := `git rev-parse --show-toplevel`

_default:
	@just --list

workshop-init:
	mkdir -p "{{repo_root}}/workshop/queries" "{{repo_root}}/workshop/ir" "{{repo_root}}/workshop/manifests" "{{repo_root}}/logs" "{{repo_root}}/build"
	printf "Workshop initialized at %s\n" "{{repo_root}}"

scaffold language query_pack:
	just workshop-init
	PYTHONPATH="{{repo_root}}/src" python - <<'PY' "{{repo_root}}" "{{language}}" "{{query_pack}}"
from pathlib import Path
import sys

from pydantree.registry.layout import WorkshopLayout

repo_root = Path(sys.argv[1])
language = sys.argv[2]
query_pack = sys.argv[3]

layout = WorkshopLayout.from_path(repo_root)
pack_dir = layout.queries_pack_dir(language, query_pack)
pack_dir.mkdir(parents=True, exist_ok=True)
placeholder = pack_dir / "highlights.scm"
if not placeholder.exists():
    placeholder.write_text("; starter query pack\n", encoding="utf-8")

print(f"Scaffolded query pack: {pack_dir.relative_to(repo_root)}")
print(f"Starter query file: {placeholder.relative_to(repo_root)}")
PY

ingest language query_pack:
	PYTHONPATH="{{repo_root}}/src" python - <<'PY' "{{repo_root}}" "{{language}}" "{{query_pack}}"
from pathlib import Path
import subprocess
import sys

from pydantree.registry.layout import WorkshopLayout

repo_root = Path(sys.argv[1])
language = sys.argv[2]
query_pack = sys.argv[3]
layout = WorkshopLayout.from_path(repo_root)

out_file = repo_root / "build" / language / query_pack / "ingest.json"
out_file.parent.mkdir(parents=True, exist_ok=True)

subprocess.run(
    [
        sys.executable,
        "-m",
        "pydantree.codegen.cli",
        "ingest",
        language,
        query_pack,
    ],
    check=True,
    cwd=repo_root,
)

print(f"Ingest artifact: {out_file.relative_to(repo_root)}")
PY

generate-models language query_pack:
	PYTHONPATH="{{repo_root}}/src" python - <<'PY' "{{repo_root}}" "{{language}}" "{{query_pack}}"
from pathlib import Path
import subprocess
import sys

from pydantree.registry.layout import WorkshopLayout

repo_root = Path(sys.argv[1])
language = sys.argv[2]
query_pack = sys.argv[3]
layout = WorkshopLayout.from_path(repo_root)
build_dir = repo_root / "build" / language / query_pack
build_dir.mkdir(parents=True, exist_ok=True)

ingest_path = build_dir / "ingest.json"
normalize_path = build_dir / "normalize.json"
emit_path = build_dir / "emit.json"
manifest_path = layout.manifest_file(language, query_pack)
models_dir = layout.generated_models_dir(language, query_pack)
manifest_path.parent.mkdir(parents=True, exist_ok=True)

subprocess.run(
    [sys.executable, "-m", "pydantree.codegen.cli", "normalize", language, query_pack],
    check=True,
    cwd=repo_root,
)
subprocess.run(
    [
        sys.executable,
        "-m",
        "pydantree.codegen.cli",
        "emit",
        language,
        query_pack,
    ],
    check=True,
    cwd=repo_root,
)
subprocess.run(
    [
        sys.executable,
        "-m",
        "pydantree.codegen.cli",
        "manifest",
        language,
        query_pack,
    ],
    check=True,
    cwd=repo_root,
)
print(f"Generated models: {models_dir.relative_to(repo_root)}")
print(f"IR artifact: {normalize_path.relative_to(repo_root)}")
print(f"Manifest: {manifest_path.relative_to(repo_root)}")
PY

validate language query_pack:
	PYTHONPATH="{{repo_root}}/src" python - <<'PY' "{{repo_root}}" "{{language}}" "{{query_pack}}"
from pathlib import Path
import subprocess
import sys

from pydantree.registry.layout import WorkshopLayout

repo_root = Path(sys.argv[1])
language = sys.argv[2]
query_pack = sys.argv[3]
layout = WorkshopLayout.from_path(repo_root)

ir_path = layout.ir_file(language, query_pack)
manifest_path = layout.manifest_file(language, query_pack)
schema_dir = repo_root / "src" / "pydantree" / "cue"

subprocess.run(
    [sys.executable, "-m", "pydantree.cli", "validate-ir", str(ir_path), "--schema-dir", str(schema_dir)],
    check=True,
    cwd=repo_root,
)
subprocess.run(
    [sys.executable, "-m", "pydantree.cli", "validate-manifest", str(manifest_path), "--schema-dir", str(schema_dir)],
    check=True,
    cwd=repo_root,
)

print("Validation complete")
PY

run-query language query_pack source:
	PYTHONPATH="{{repo_root}}/src" python - <<'PY' "{{repo_root}}" "{{language}}" "{{query_pack}}" "{{source}}"
from pathlib import Path
import subprocess
import sys

from pydantree.registry.layout import WorkshopLayout

repo_root = Path(sys.argv[1])
language = sys.argv[2]
query_pack = sys.argv[3]
source_key = sys.argv[4]
layout = WorkshopLayout.from_path(repo_root)

query_dir = layout.queries_pack_dir(language, query_pack)
query_files = sorted(query_dir.glob("*.scm"))
if not query_files:
    raise SystemExit(f"No .scm files found in {query_dir}")

matches = sorted((repo_root / "tests" / "fixtures" / language / query_pack).glob(f"{source_key}.*"))
if not matches:
    raise SystemExit(
        "Source alias not found. Expected a fixture file at "
        f"tests/fixtures/{language}/{query_pack}/{source_key}.*"
    )
source_path = matches[0]
query_path = query_files[0]

subprocess.run(
    ["tree-sitter", "query", str(query_path), str(source_path)],
    check=True,
    cwd=repo_root,
)
PY

doctor language query_pack:
	PYTHONPATH="{{repo_root}}/src" python - <<'PY' "{{repo_root}}" "{{language}}" "{{query_pack}}"
from pathlib import Path
import subprocess
import sys

from pydantree.registry.layout import WorkshopLayout

repo_root = Path(sys.argv[1])
language = sys.argv[2]
query_pack = sys.argv[3]
layout = WorkshopLayout.from_path(repo_root)
queries_dir = layout.queries_pack_dir(language, query_pack)
manifest_path = layout.manifest_file(language, query_pack)

subprocess.run(
    [
        sys.executable,
        "-m",
        "pydantree.cli",
        "doctor",
        "--queries-dir",
        str(queries_dir),
        "--manifest",
        str(manifest_path),
    ],
    check=False,
    cwd=repo_root,
)
PY
