"""
pydantree_sitter_grammar.pipeline — the native build pipeline.

    Grammar (IR or builder) -> grammar.json -> tree-sitter generate
    -> parser.c -> gcc -> .so -> load -> parse

All CLI/toolchain interaction lives here so evidence (raw stdout/stderr) can
be captured verbatim. Content-addressed cache keyed on
`sha256(grammar.json) + ABI version + toolchain version`.

Toolchain facts (Phase 0, not re-derived):

- `tree-sitter generate <grammar.json>` works directly; grammar.js is bypassed.
- Without a `tree-sitter.json` config the CLI falls back to ABI 14; with
  `{"metadata": {"version": "0.1.0"}}` it generates ABI 15 (matches the
  Python bindings 0.26.0, which support ABI 13..15).
- Unresolved conflicts: exit 1, NO parser.c written, first conflict only,
  machine report on stderr with `--json` (handled by pydantree_sitter_grammar.conflicts).
- Unused rules are silently pruned by the CLI — run the analyzer first.
- A compiled .so exports `tree_sitter_<grammar_name>`; load it via a PyCapsule
  named "tree_sitter.Language" (int pointer is deprecated in 0.26) — see
  pydantree_sitter_grammar.language.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .ir import GrammarModel

ABI_15_CONFIG = {"metadata": {"version": "0.1.0"}}

# the loader shim shipped inside a packaged bundle: it delegates to pydantree_sitter's
# shared loading contract (the ONE implementation, CONCEPT §8)
BUNDLE_LOADER_SOURCE = '''\
"""Load this bundle's grammar into a tree_sitter.Language (B-free)."""
from pathlib import Path
from pydantree_sitter.loader import load_bundle


def language():
    return load_bundle(Path(__file__).resolve().parent).language
'''


# ---------------------------------------------------------------------------
# toolchain probing
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Toolchain:
    tree_sitter_version: str
    gcc_version: str
    python_abi: str

    @property
    def key(self) -> str:
        return f"{self.tree_sitter_version}|{self.gcc_version}|{self.python_abi}"


def detect_toolchain() -> Toolchain:
    """Probe the CLI + compiler versions (cached in-process via
    functools.lru_cache — `detect_toolchain.cache_clear()` documented
    reset; tests that swap the toolchain env call it)."""
    ts = subprocess.run(
        ["tree-sitter", "--version"], capture_output=True, text=True, check=False)
    ts_version = ts.stdout.strip() or ts.stderr.strip() or "unknown"
    gcc = subprocess.run(
        ["gcc", "--version"], capture_output=True, text=True, check=False)
    gcc_version = gcc.stdout.splitlines()[0].strip() if gcc.stdout else "unknown"
    return Toolchain(
        tree_sitter_version=ts_version,
        gcc_version=gcc_version,
        python_abi=_python_abi(),
    )


def _python_abi() -> str:
    """The ABI: the actual tree_sitter.LANGUAGE_VERSION when available (the
    bindings' floor), else the TSGRAMMAR_ABI env override, else "15"."""
    try:
        import tree_sitter as _ts
        return str(_ts.LANGUAGE_VERSION)
    except Exception:
        return os.environ.get("TSGRAMMAR_ABI", "15")


import functools as _functools
detect_toolchain = _functools.lru_cache(maxsize=1)(detect_toolchain)


def grammar_hash(model: GrammarModel) -> str:
    """Content-addressed key: sha256 over the canonical grammar.json bytes."""
    return hashlib.sha256(
        model.model_dump_json(indent=2, exclude_none=True).encode()
    ).hexdigest()


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

def run_generate(grammar_json: Path, *, abi15: bool = True) -> subprocess.CompletedProcess:
    """Run `tree-sitter generate --json` on the given grammar.json (D10: the
    conflict report is JSON on stderr — ONE run, no failure-path re-run).
    Returns the raw CompletedProcess for verbatim capture."""
    dirpath = grammar_json.parent
    if abi15:
        cfg = dirpath / "tree-sitter.json"
        if not cfg.exists():
            cfg.write_text(json.dumps(ABI_15_CONFIG))
    cmd = ["tree-sitter", "generate", "--json", str(grammar_json)]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(dirpath), check=False)


def generate(model: GrammarModel, workdir: Path) -> subprocess.CompletedProcess:
    """Emit grammar.json into `workdir` and run the generator (always
    --json, D10). Returns the raw CompletedProcess; on success parser.c lands
    in workdir/src/parser.c."""
    json_path = model.emit_bundle(workdir)
    return run_generate(json_path)


# ---------------------------------------------------------------------------
# compile
# ---------------------------------------------------------------------------

def compile_parser(src_dir: Path, so_path: Path, *,
                   scanner: Path | None = None) -> subprocess.CompletedProcess:
    """gcc -O2 -fPIC -shared parser.c (+ optional scanner.c) -> .so."""
    cmd = [
        "gcc", "-O2", "-fPIC", "-shared",
        "-I", str(src_dir),
        "-I", str(src_dir / "tree_sitter"),
        str(src_dir / "parser.c"),
    ]
    if scanner is not None and scanner.exists():
        cmd.append(str(scanner))
    cmd += ["-o", str(so_path)]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------

def default_cache_dir() -> Path:
    """The pipeline cache root (014 7.3: `PYDANTREE_SITTER_CACHE`; the legacy
    `TSGRAMMAR_CACHE` spelling is still honored as a fallback)."""
    env = os.environ.get("PYDANTREE_SITTER_CACHE") or \
        os.environ.get("TSGRAMMAR_CACHE")
    return Path(env if env else str(Path.home() / ".cache" / "pydantree_sitter_grammar"))


@dataclass
class BuildResult:
    """The product of a build: paths + the raw generator evidence."""
    grammar_json: Path
    src_dir: Path
    parser_c: Path
    so_path: Path
    node_types_json: Path
    node_schema_json: Path | None = None
    generate_proc: subprocess.CompletedProcess | None = None
    compile_proc: subprocess.CompletedProcess | None = None
    cached: bool = False

    def language(self, grammar_name: str | None = None):
        from .language import load_language
        return load_language(self.so_path, grammar_name)

    def node_schema(self):
        """The derived node-schema (pydantree_sitter.NodeSchema) — the bridge artifact.
        Returns None if the build predates node-schema emission."""
        if self.node_schema_json is None or not self.node_schema_json.exists():
            return None
        from pydantree_sitter.schema import NodeSchema
        return NodeSchema.from_node_types_json(self.node_schema_json)

    def package(self, dir: Path | str, *,
                include_loader: bool = True,
                typed_api: bool = False) -> Path:
        """Package the build into a shippable bundle directory — delegates
        to the ONE bundle writer `write_bundle` (D10)."""
        return write_bundle(self, dir, include_loader=include_loader,
                            typed_api=typed_api)


def write_bundle(result: BuildResult, dir: Path | str, *,
                 include_loader: bool = True,
                 typed_api: bool = False,
                 metadata: dict | None = None) -> Path:
    """THE ONE bundle writer (D10): package a BuildResult into a shippable
    bundle directory (Phase 5 — the artifact seam in production):

        grammar.so        the compiled parser (export tree_sitter_<name>)
        node-schema.json  the derived node-schema (bridge artifact)
        tree-sitter.json  bundle metadata (name = the export symbol)
        loader.py         a thin shim over pydantree_sitter.loader.load_bundle
        typed_api.py      REAL typed CST accessors (014 §5/D7, typed_api=True)

    Consumed B-free — pydantree_sitter.Language.load_bundle(dir) — or by
    anyone with pydantree_sitter + tree_sitter (loader.py delegates to the
    shared loading contract, CONCEPT §8). Returns the bundle dir.
    """
    import shutil as _shutil
    bundle = Path(dir)
    bundle.mkdir(parents=True, exist_ok=True)
    _shutil.copyfile(result.so_path, bundle / "grammar.so")
    schema_rel = None
    if result.node_schema_json is not None and result.node_schema_json.exists():
        _shutil.copyfile(result.node_schema_json, bundle / "node-schema.json")
        schema_rel = "node-schema.json"
    if typed_api and result.node_schema_json is not None \
            and result.node_schema_json.exists():
        from pydantree_sitter.codegen import write_typed_api
        from pydantree_sitter.schema import NodeSchema
        schema = NodeSchema.from_node_types_json(result.node_schema_json)
        write_typed_api(schema, bundle / "typed_api.py",
                        module_name=f"typed_api_{result.so_path.stem}")
    meta = metadata if metadata is not None else {
        "bundle_format": 2,          # D12: versioned artifact contract
        "name": result.so_path.stem,
        "artifact": "grammar.so",
        "schema": schema_rel,
        "abi": os.environ.get("TSGRAMMAR_ABI", "15"),
        "toolchain": detect_toolchain().tree_sitter_version,
    }
    (bundle / "tree-sitter.json").write_text(json.dumps(meta, indent=2))
    if include_loader:
        (bundle / "loader.py").write_text(BUNDLE_LOADER_SOURCE)
    return bundle


def _cache_node_schema(entry: Path, model: GrammarModel) -> Path:
    """node-schema.json := the cache entry's src/node-types.json, byte-for-byte.

    The schema IS the CLI's byproduct (014 refactor D3 — the hand-port
    of node_types.rs is deleted; there is no other derivation). On a warm cache entry
    that predates this (no node-schema.json yet), re-run generate over the
    entry's grammar.json — the CLI is the authoritative source. Returns the
    node-schema.json path.
    """
    schema_path = entry / "node-schema.json"
    if schema_path.exists():
        return schema_path
    node_types = entry / "src" / "node-types.json"
    if not node_types.exists():
        gen = run_generate(entry / "grammar.json")
        if gen.returncode != 0:
            raise GenerateError(
                model, gen,
                detail="warm-cache backfill: re-running generate to "
                       "recover node-types.json (the schema's only source)")
        node_types = entry / "src" / "node-types.json"
    shutil.copyfile(node_types, schema_path)
    return schema_path


def build(model: GrammarModel, *, cache_dir: Path | None = None,
          toolchain: Toolchain | None = None,
          grammar_name: str | None = None,
          scanner: Path | str | None = None,
          check: bool = True) -> BuildResult:
    """Full pipeline with content-addressed caching.

    Cache key: sha256(grammar.json) + ABI version + toolchain version. On a
    hit, skip generate+gcc entirely. `grammar_name` defaults to the grammar's
    `name` (the .so export symbol must match). `scanner` optionally points at
    an external-scanner scanner.c to copy into the build (grammars with
    `externals` need one to link). The bundle's node-schema.json is the
    generate run's node-types.json byproduct, copied byte-for-byte (D3).

    `check` (default True, D10): the static analyzer (checks.assert_clean)
    runs BEFORE generate — analyzer errors abort the build; warnings surface
    to the caller. Pass `check=False` to skip.
    """
    if check:
        from .checks import assert_clean, warnings as check_warnings
        assert_clean(model)
        for w in check_warnings(model):
            pass  # surfaced to the caller's renderer; non-fatal
    cache_dir = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    toolchain = toolchain or detect_toolchain()
    name = grammar_name or model.name
    scanner = Path(scanner) if scanner is not None else None

    h = grammar_hash(model)
    tc_digest = hashlib.sha256(toolchain.key.encode()).hexdigest()[:12]
    key = f"{h}-{tc_digest}"
    if scanner is not None and scanner.exists():
        # the .so depends on the scanner.c too — content-address it in the
        # cache key so a scanner build and a scanner-less build don't collide
        scanner_digest = hashlib.sha256(scanner.read_bytes()).hexdigest()[:12]
        key = f"{h}-{scanner_digest}-{tc_digest}"
    entry = cache_dir / key
    so_path = entry / f"{name}.so"
    grammar_json = entry / "grammar.json"

    if so_path.exists() and grammar_json.exists():
        _cache_node_schema(entry, model)
        return BuildResult(
            grammar_json=grammar_json,
            src_dir=entry / "src",
            parser_c=entry / "src" / "parser.c",
            so_path=so_path,
            node_types_json=entry / "src" / "node-types.json",
            node_schema_json=entry / "node-schema.json",
            cached=True,
        )

    # ---- miss: build into a fresh work dir, then promote into the cache ----
    work = cache_dir / ".work" / key
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    json_path = model.emit_bundle(work)
    gen = run_generate(json_path)
    if gen.returncode != 0:
        # leave evidence behind; the caller decides how to render the failure
        raise GenerateError(model, gen)

    src_dir = work / "src"
    parser_c = src_dir / "parser.c"
    if not parser_c.exists():
        raise GenerateError(
            model, gen,
            detail=f"generate exited 0 but wrote no parser.c (check stdout:\n{gen.stdout})")

    # scanner.c sits beside parser.c (canonical location); fall back to the
    # workdir root for hand-authored layouts; an explicit `scanner=` arg
    # (for grammars with externals) is copied into the build first.
    if scanner is not None:
        shutil.copy(scanner, work / "scanner.c")
    scanner = (src_dir / "scanner.c") if (src_dir / "scanner.c").exists() \
        else work / "scanner.c"
    if model.externals and not scanner.exists():
        # the airtight escape hatch: a grammar with externals MUST link a C
        # scanner, and the error says so before gcc produces a link failure
        raise ExternalScannerRequiredError(
            model,
            externals=[_external_name(e) for e in model.externals],
            detail=(f"grammar {model.name!r} declares externals but no "
                    f"scanner.c was supplied — pass scanner=<path> to "
                    f"build()/build_builder() (external tokens are provided "
                    f"by a C scanner at runtime; see the pymini example)."))
    work_so = work / f"{name}.so"
    cc = compile_parser(src_dir, work_so, scanner=scanner)
    if cc.returncode != 0:
        raise CompileError(model, cc)

    # promote into the cache (D10): build in a sibling work dir, then
    # rename-if-absent — if a concurrent build won the race, discard ours
    entry.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(work, entry)
    except FileExistsError:
        shutil.rmtree(work, ignore_errors=True)

    node_types = entry / "src" / "node-types.json"
    _cache_node_schema(entry, model)
    return BuildResult(
        grammar_json=entry / "grammar.json",
        src_dir=entry / "src",
        parser_c=entry / "src" / "parser.c",
        so_path=entry / f"{name}.so",
        node_types_json=node_types,
        node_schema_json=entry / "node-schema.json",
        generate_proc=gen,
        compile_proc=cc,
        cached=False,
    )


def _resolve_grammar_json(grammar_dir: Path) -> Path:
    """The grammar.json in a source dir: `<dir>/grammar.json` (B's own
    emitted layout) or `<dir>/src/grammar.json` (the standard community
    repo layout)."""
    for cand in (grammar_dir / "grammar.json", grammar_dir / "src" / "grammar.json"):
        if cand.exists():
            return cand
    raise FileNotFoundError(
        f"not a grammar source dir: {grammar_dir} (no grammar.json or "
        f"src/grammar.json)")


def build_from_source_dir(src_dir: Path | str, *,
                          cache_dir: Path | None = None,
                          name: str | None = None,
                          scanner: Path | str | None = None) -> BuildResult:
    """A community grammar SOURCE dir -> BuildResult (D10: schema_tool's
    path merges into the pipeline — same cache, same errors, same bundle
    writer).

    Accepts `<dir>/grammar.json` (B's own layout) or `<dir>/src/grammar.json`
    (the standard community layout); the external scanner is picked up from
    the source (beside grammar.json, or `<dir>/scanner.c`) when present.
    NEVER touches the author's checkout (F-B11): the grammar is parsed into
    the IR and built content-addressed; all work happens inside the cache
    dir. Package the result with `write_bundle`.
    """
    src_dir = Path(src_dir)
    grammar_json = _resolve_grammar_json(src_dir)
    model = GrammarModel.model_validate_json(grammar_json.read_text())
    if scanner is None:
        for cand in (grammar_json.parent / "scanner.c", src_dir / "scanner.c"):
            if cand.exists():
                scanner = cand
                break
    # community grammars are not ours to analyze (the analyzer's unused-rule
    # guidance is for AUTHORS) — build with check=False
    return build(model, cache_dir=cache_dir, check=False,
                 grammar_name=name or model.name, scanner=scanner)


def build_builder(g, *, cache_dir=None, **kw) -> BuildResult:
    """build() for a builder DSL Grammar (builds the IR first).

    When `tree-sitter generate` fails on an unresolved conflict, re-runs with
    `--json` and raises `GrammarConflictError` (remapped to the author's
    per-production DSL source sites) instead of a bare `GenerateError` — the
    fix-one-rerun loop depends on this.
    """
    model = g.build()
    try:
        return build(model, cache_dir=cache_dir, **kw)
    except GenerateError as e:
        # the conflict report is JSON on the SAME run's stderr (D10 — the
        # --json flag is always on): remap to the author's per-production
        # DSL source sites, no second generate
        if e.proc is not None and e.proc.returncode == 1:
            from .conflicts import parse_conflict_json, remap_from_proc
            if parse_conflict_json(e.proc.stderr) is not None:
                _conflict, err = remap_from_proc(g, e.proc)
                raise err from None
        raise


def build_loop(g, *, fix=None, cache_dir=None, max_attempts: int = 8,
               **kw):
    """The fix-one-rerun loop (first-class Phase-3 API).

    Yields a `GrammarConflictError` for each conflicted generate attempt — the
    error names the per-production DSL site and the generator's suggested
    fixes — then calls `fix(error, g)` (which should mutate `g`, e.g. via
    `g.replace_rule(...)` or `g.conflict(...)`) and re-runs. Generate is
    sub-second, so one conflict per iteration is the natural cadence (the CLI
    is fail-fast: first conflict only). On a clean generate, yields the
    `BuildResult` and returns. Raises after `max_attempts` without a clean
    generate.

    Usage:
        def fix(error, g):
            ...  # apply the suggested fix, one at a time
        for event in tg.build_loop(g, fix=fix):
            if isinstance(event, tg.GrammarConflictError):
                print(event)          # the bite, local and actionable
            else:
                result = event        # clean generate -> .so
    """
    from .conflicts import GrammarConflictError
    for attempt in range(max_attempts):
        try:
            result = build_builder(g, cache_dir=cache_dir, **kw)
            yield result
            return
        except GrammarConflictError as e:
            yield e
            if fix is not None:
                fix(e, g)
    raise RuntimeError(
        f"build_loop: no clean generate after {max_attempts} attempts "
        f"(grammar {g.name!r})")


def debug_states(g, rule_name: str, *, workdir: Path | None = None,
                 json_report: bool = False):
    """Wrapper over `tree-sitter generate --report-states-for-rule <name>` —
    the 'why is my unary/^ interaction wrong?' surface. Emits the grammar into
    `workdir` (a temp dir by default) and returns the raw CLI output text.
    Rule name `-` reports every rule."""
    import tempfile

    work = Path(workdir) if workdir is not None \
        else Path(tempfile.mkdtemp(prefix="pydantree_sitter_grammar-states-"))
    work.mkdir(parents=True, exist_ok=True)
    json_path = g.emit_bundle(work)
    cmd = ["tree-sitter", "generate", str(json_path),
           "--report-states-for-rule", rule_name]
    if json_report:
        cmd.append("--json")
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          cwd=str(work), check=False)
    body = proc.stdout if proc.stdout.strip() else proc.stderr
    return proc.returncode, body, proc


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------

class PipelineError(Exception):
    """Base for pipeline failures, carrying the raw subprocess output."""

    def __init__(self, message: str, proc: subprocess.CompletedProcess | None = None):
        self.proc = proc
        super().__init__(message)
        if proc is not None:
            self.raw_stdout = proc.stdout
            self.raw_stderr = proc.stderr


def _external_name(e) -> str:
    """The external token's visible name: TOKEN(content) unwraps to the
    content's value; a bare STRING is its literal; a SYMBOL its rule name."""
    from .ir import StrNode, SymbolNode, TokenNode
    if isinstance(e, TokenNode):
        e = e.content
    if isinstance(e, StrNode):
        return e.value
    if isinstance(e, SymbolNode):
        return e.name
    return str(e)


class GenerateError(PipelineError):
    def __init__(self, model: GrammarModel, proc: subprocess.CompletedProcess,
                 detail: str = ""):
        msg = (
            f"tree-sitter generate failed for grammar {model.name!r} "
            f"(exit {proc.returncode}). {detail}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
        super().__init__(msg, proc)


class CompileError(PipelineError):
    def __init__(self, model: GrammarModel, proc: subprocess.CompletedProcess):
        msg = (
            f"gcc failed compiling parser for grammar {model.name!r} "
            f"(exit {proc.returncode}).\n--- stdout ---\n{proc.stdout}"
            f"\n--- stderr ---\n{proc.stderr}"
        )
        super().__init__(msg, proc)


class ExternalScannerRequiredError(PipelineError):
    """A grammar declares `externals` but no scanner.c was supplied (Phase 5:
    the external-scanner escape hatch made airtight — before gcc fails with a
    link error, the author gets the fix)."""

    def __init__(self, model: GrammarModel, *, externals: list[str],
                 detail: str = ""):
        self.externals = externals
        super().__init__(
            f"external scanner required: grammar {model.name!r} declares "
            f"external token(s) {externals} but no scanner.c was provided. "
            f"{detail}")
