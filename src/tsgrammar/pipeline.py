"""
tsgrammar.pipeline — the native build pipeline.

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
  machine report on stderr with `--json` (handled by tsgrammar.conflicts).
- Unused rules are silently pruned by the CLI — run the analyzer first.
- A compiled .so exports `tree_sitter_<grammar_name>`; load it via a PyCapsule
  named "tree_sitter.Language" (int pointer is deprecated in 0.26) — see
  tsgrammar.language.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .grammar import Grammar as GrammarModel

ABI_15_CONFIG = {"metadata": {"version": "0.1.0"}}


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
    """Probe the CLI + compiler versions (cached in-process)."""
    if detect_toolchain._cache is not None:  # type: ignore[attr-defined]
        return detect_toolchain._cache  # type: ignore[attr-defined]
    ts = subprocess.run(
        ["tree-sitter", "--version"], capture_output=True, text=True, check=False)
    ts_version = ts.stdout.strip() or ts.stderr.strip() or "unknown"
    gcc = subprocess.run(
        ["gcc", "--version"], capture_output=True, text=True, check=False)
    gcc_version = gcc.stdout.splitlines()[0].strip() if gcc.stdout else "unknown"
    tc = Toolchain(
        tree_sitter_version=ts_version,
        gcc_version=gcc_version,
        python_abi=os.environ.get("TSGRAMMAR_ABI", "15"),
    )
    detect_toolchain._cache = tc  # type: ignore[attr-defined]
    return tc


detect_toolchain._cache = None  # type: ignore[attr-defined]


def grammar_hash(model: GrammarModel) -> str:
    """Content-addressed key: sha256 over the canonical grammar.json bytes."""
    return hashlib.sha256(
        model.model_dump_json(indent=2, exclude_none=True).encode()
    ).hexdigest()


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

def run_generate(grammar_json: Path, *, json_report: bool = False,
                 abi15: bool = True) -> subprocess.CompletedProcess:
    """Run `tree-sitter generate` on the given grammar.json. Returns the raw
    CompletedProcess (stdout/stderr/returncode) for verbatim capture."""
    dirpath = grammar_json.parent
    if abi15:
        cfg = dirpath / "tree-sitter.json"
        if not cfg.exists():
            cfg.write_text(json.dumps(ABI_15_CONFIG))
    cmd = ["tree-sitter", "generate", str(grammar_json)]
    if json_report:
        cmd.append("--json")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(dirpath), check=False)


def generate(model: GrammarModel, workdir: Path,
             *, json_report: bool = False) -> subprocess.CompletedProcess:
    """Emit grammar.json into `workdir` and run the generator. Returns the
    raw CompletedProcess; on success parser.c lands in workdir/src/parser.c."""
    json_path = model.emit_bundle(workdir)
    return run_generate(json_path, json_report=json_report)


# ---------------------------------------------------------------------------
# compile
# ---------------------------------------------------------------------------

def compile_parser(src_dir: Path, so_path: Path, *,
                   scanner: Path | None = None) -> subprocess.CompletedProcess:
    """gcc -O2 -fPIC -shared parser.c (+ optional scanner.c) -> .so."""
    cmd = [
        "gcc", "-O2", "-fPIC", "-shared",
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
    return Path(os.environ.get("TSGRAMMAR_CACHE", str(Path.home() / ".cache" / "tsgrammar")))


@dataclass
class BuildResult:
    """The product of a build: paths + the raw generator evidence."""
    grammar_json: Path
    src_dir: Path
    parser_c: Path
    so_path: Path
    node_types_json: Path
    generate_proc: subprocess.CompletedProcess | None = None
    compile_proc: subprocess.CompletedProcess | None = None
    cached: bool = False

    def language(self, grammar_name: str | None = None):
        from .language import load_language
        return load_language(self.so_path, grammar_name)


def build(model: GrammarModel, *, cache_dir: Path | None = None,
          toolchain: Toolchain | None = None,
          grammar_name: str | None = None,
          scanner: Path | str | None = None) -> BuildResult:
    """Full pipeline with content-addressed caching.

    Cache key: sha256(grammar.json) + ABI version + toolchain version. On a
    hit, skip generate+gcc entirely. `grammar_name` defaults to the grammar's
    `name` (the .so export symbol must match). `scanner` optionally points at
    an external-scanner scanner.c to copy into the build (grammars with
    `externals` need one to link).
    """
    cache_dir = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    toolchain = toolchain or detect_toolchain()
    name = grammar_name or model.name
    scanner = Path(scanner) if scanner is not None else None

    h = grammar_hash(model)
    tc_digest = hashlib.sha256(toolchain.key.encode()).hexdigest()[:12]
    key = f"{h}-{tc_digest}"
    entry = cache_dir / key
    so_path = entry / f"{name}.so"
    grammar_json = entry / "grammar.json"

    if so_path.exists() and grammar_json.exists():
        return BuildResult(
            grammar_json=grammar_json,
            src_dir=entry / "src",
            parser_c=entry / "src" / "parser.c",
            so_path=so_path,
            node_types_json=entry / "src" / "node-types.json",
            cached=True,
        )

    # ---- miss: build into a fresh work dir, then promote into the cache ----
    work = cache_dir / ".work" / key
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    json_path = model.emit_bundle(work)
    gen = run_generate(json_path, json_report=False)
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
    work_so = work / f"{name}.so"
    cc = compile_parser(src_dir, work_so, scanner=scanner)
    if cc.returncode != 0:
        raise CompileError(model, cc)

    # promote into the cache (atomic-ish: rename the work dir)
    entry.parent.mkdir(parents=True, exist_ok=True)
    if entry.exists():
        shutil.rmtree(entry)
    work.rename(entry)

    node_types = entry / "src" / "node-types.json"
    return BuildResult(
        grammar_json=entry / "grammar.json",
        src_dir=entry / "src",
        parser_c=entry / "src" / "parser.c",
        so_path=entry / f"{name}.so",
        node_types_json=node_types,
        generate_proc=gen,
        compile_proc=cc,
        cached=False,
    )


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
        if e.proc is not None and e.proc.returncode == 1:
            import tempfile

            from .conflicts import parse_conflict_json, remap_from_proc
            with tempfile.TemporaryDirectory(prefix="tsgrammar-remap-") as td:
                json_path = model.emit_bundle(Path(td))
                proc = run_generate(json_path, json_report=True)
                if parse_conflict_json(proc.stderr) is not None:
                    _conflict, err = remap_from_proc(g, proc)
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
        else Path(tempfile.mkdtemp(prefix="tsgrammar-states-"))
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
