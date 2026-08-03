# Phase 7, item 3 — the wasm runtime + the scanner library: Findings & Verdict

**Date:** 2026-08-03
**Status:** COMPLETE
**Verdicts:**
- **Run A (wasm): GO on the seam extension (landed), NO-GO on A taking a
  wasm runtime dependency now.** The probe is REAL end to end: a rust.wasm
  built by the tree-sitter CLI + emcc 5.0.7, loaded and parsed through
  wasmtime 29.0.0 via the tree-sitter C library's official wasm store, at a
  measured 1.47–1.85× the native parse cost (median 1.6× — the CONCEPT §11.5
  note confirmed, slightly worse than its midpoint). The decisive fact is
  NOT perf: **py-tree-sitter 0.26 has NO wasm support** — a wasm language
  needs a parser bound to a wasm store (tree-sitter's `wasm_store.c`), which
  the standard binding never links. A wasm load in A means FORKING the
  binding (compiling libtree-sitter with `TREE_SITTER_FEATURE_WASM` against
  the version-matched wasmtime C API), plus a 16 MB wasmtime native
  dependency in the light install — for a portability win the per-platform
  wheels already deliver (Phase-6 GO). Landed anyway (the seam's natural
  extension point): `tscore.loader` dispatches on the artifact extension, a
  `.wasm` artifact raises `WasmRuntimeUnavailableError` with the exact state
  of the path, and the real load works when the probe's runtime is wired
  (TSGRAMMAR_WASM_LIB / TSGRAMMAR_WASMTIME_LIB) — tests pinned both ways.
- **Run B (scanner library): GO.** Two REAL per-language scanners landed on
  the airtight mechanism — the real-Python logical-line indentation scanner
  (adapted from tree-sitter-python) and the bash multi-heredoc scanner with
  the pending-delimiter queue, `<<-` indent-stripping, and quoted delimiters
  (adapted from tree-sitter-bash). Both hit the two Phase-6 gotchas LIVE
  (the mid-whitespace dispatch and both-externals-valid-in-one-state each
  caused a real bug first — see §2). The mechanism (scanner=,
  content-addressed cache keying, `ExternalScannerRequiredError`) held with
  zero leaks over real upstream semantics.

Re-run:

```bash
devenv shell -- python -m pytest tests/                 # 170 green + 1 skip
devenv shell -- python .scratch/009-phase7/probe_wasm_runtime.py   # (needs
    # the probe's runtime in /tmp — see evidence/rA_artifact_build.txt)
devenv shell -- python .scratch/009-phase7/bench_wasm_vs_native.py
```

Evidence (verbatim): `.scratch/009-phase7/evidence/rA_artifact_build.txt`
(toolchain + artifact + runtime + perf), `rA_rust_grammar.wasm` (the real
artifact), `rA_wasm_perf.txt` (three benchmark runs).

---

## 1. Run A — the wasm runtime: REAL probe, NO-GO for A's budget

### 1.1 The toolchain probe

No emscripten in the devenv packages. `nix shell nixpkgs#emscripten` gives
**emcc 5.0.7-git** (a real toolchain install: emscripten 5.0.7 +
emscripten-llvm + clang/llvm 22.1.8 — a multi-hundred-MB nix closure, ~10
store paths). The tree-sitter CLI's `build --wasm` needs emcc on PATH (it
also supports docker/podman — the CLI's own fallback order).

### 1.2 The artifact probe

`tree-sitter generate` + `tree-sitter build --wasm -o rust.wasm` over the
REAL rust grammar source (`tests/fixtures/rust`) produces a **1,114,265-byte
standalone module**: a SIDE_MODULE importing ONLY libc (`calloc`, `free`,
`iswspace`, `iswalpha`) + memory + dylink globals/table; exporting only
`tree_sitter_rust` + ctors. The full parse tables + lex functions live in
the module; the HOST parse engine is the tree-sitter C library's
`wasm_store.c`, which instantiates the module and copies the language struct
out of wasm memory.

### 1.3 The runtime probe (the honest test)

The runtime is wasmtime **29.0.0** — the exact version tree-sitter 0.25.3
pins in Cargo.lock — via the wasmtime Python wheel's `_libwasmtime.so`
(16 MB), with `libtree-sitter` compiled `-DTREE_SITTER_FEATURE_WASM` against
wasmtime's C API headers (v29.0.0 tag) using gcc 14.2.1 (2 minutes, one
`conf.h` generation step). The A-side bridge is ctypes over
`ts_wasm_store_new/load_language` + `ts_parser_*` + `ts_node_*`
(`probe_wasm_runtime.py`). Result: **a real parse** of the rust grammar
through the real runtime — abi=15, correct sexp
(`function_item`/`let_declaration`/`macro_invocation`/`if_expression`…),
`has_error=False`. This is the official path the CLI/editor ecosystem uses,
not a toy.

### 1.4 The perf probe

Same engine, same 262 KB rust corpus, median of 200 parses, native `.so` vs
the `.wasm` grammar (evidence `rA_wasm_perf.txt`, three runs):

| run | native | wasm | ratio |
|---|---|---|---|
| 1 | 73.9 ms | 108.9 ms | 1.47× |
| 2 | 61.1 ms | 113.2 ms | 1.85× |
| 3 | 69.8 ms | 108.2 ms | 1.55× |

**wasm/native ≈ 1.5–1.9× (median 1.6×)** — CONCEPT §11.5's "~1.5–2×"
confirmed. (The first ever run showed 2.14×; that was a wasmtime JIT
warm-up — the medians are stable.)

### 1.5 The distribution question — the verdict

What a `.wasm` bundle buys: one artifact for every platform (no per-platform
native build). What it costs:

1. **A binding fork, not a dependency pin (the decisive fact).** py-tree-sitter
   0.26 (the `tree-sitter>=0.26` floor every distribution pins) has NO wasm
   support. A wasm language cannot be wrapped in a `tree_sitter.Language`
   capsule; the parser must hold a wasm store. The official support lives in
   the C library's `wasm_store.c` behind `TREE_SITTER_FEATURE_WASM` +
   wasmtime C API — a custom build, version-matched to the tree-sitter pin
   (wasmtime 29.x for CLI 0.25.3). The Phase-7 probe built exactly this in
   ~30 minutes; A shipping it means maintaining a forked binding.
2. **A 16 MB wasmtime native dependency in the light install** (the wasmtime
   Python wheel) — the light side gains a native runtime, undoing part of
   the "light" story.
3. **The emscripten toolchain stays at build time** (CONCEPT §4.7's own line:
   wasm removes the compiler-at-load-time problem, not the
   compiler-at-build-time problem) — B gains a multi-hundred-MB toolchain
   for the wasm variant.
4. **The 1.6× perf tax** (measured).

The counterfactual: per-platform native wheels already carry the portability
story (Phase-6 Run 1: a light install over native wheels runs the full
checked extraction, B-free, byte-identical). The honest comparison: wasm
buys "one CI job instead of N" at the cost above. **Not worth A's dependency
budget now** — same verdict Phase 6 reached on less evidence.

**What landed (go-with-changes on the seam):** `tscore.loader` now dispatches
on the bundle artifact extension — a `.wasm` artifact raises
`WasmRuntimeUnavailableError` naming exactly what's missing and what it would
take (the probe's evidence), or loads through the real wasmtime bridge when
the runtime is wired (env-pointed, `src/tscore/_wasm_bridge.py`). The
one-line `Language.load_bundle` surface is unchanged for native bundles;
over a wasm bundle it reports the honest state. `tests/test_wasm.py` pins
the dispatch, the error, and the env-gated real load over the probe's
rust.wasm.

**One honest caveat on the landed surface:** `tsquery.Language.load_bundle`
over a WASM bundle returns the `tscore` `WasmLanguage` (a minimal parse
surface) but cannot wrap it in the py-tree-sitter `tree_sitter.Language` A's
DSL machinery expects — the standard binding has no wasm store. That is the
finding in code form: wasm in A is a binding-ownership question first.

## 2. Run B — the scanner library: GO, two real per-language copies

### 2.1 `py_indent_scanner.c` — the real Python logical-line semantics

Adapted from tree-sitter-python's `src/scanner.c` (read, mechanism adapted —
NOT copied wholesale). The mini-grammar `pyindent`
(`.scratch/009-phase7/pyindent.py`) uses the REAL header shape —
`if x: NEWLINE INDENT stmt+ DEDENT` — which exercises the two-call
zero-width cadence the pymini seed deliberately avoids (NEWLINE at the
newline, INDENT at the same position; Phase-5 appendix fact 5). The real
semantics under test:

- **comment-only lines emit NO NEWLINE** (skipped inside the scanner);
  **blank lines too**; **a trailing comment after an expression is NOT a
  line ending** (the scanner declines; the grammar's comment extra consumes
  it, the NEWLINE comes after) — the pymini seed's simplified comment
  handling is superseded;
- **backslash continuations** keep the logical line open (the upstream
  `line_continuation` extra + the scanner's own backslash branch);
- **`\r`/`\f` reset the indent column; `\t` = 8 columns**;
- the upstream **comment-aware DEDENT guard**
  (`first_comment_indent_length < current`).

Corpus: 6 cases incl. the real-semantics ones; parse-error case: a header
with no body (`if x:` — `stmt+` requires content).

### 2.2 `bash_heredoc_scanner.c` — the bash multi-heredoc pending queue

Adapted from tree-sitter-bash's `src/scanner.c`. The mini-grammar `bashmini`
consumes heredoc bodies in OPENING order (real bash reads `cat <<A <<B` as
A's body then B's body). The mechanism is the hmini one (a single
HEREDOC_BODY token INCLUDING the delimiter line — the TSLexer struct is NOT
copyable for peeking, a fact the upstream's peek-heavy design doesn't need);
the queue + delimiter flags are the bash adaptation:

- **the pending-delimiter QUEUE** (`MAX_PENDING=8`, FIFO served, serialized
  in the scanner state) — several heredocs opened on one command line;
- **`<<-` indent-stripped** delimiter lines (leading tabs allowed);
- **quoted delimiters** (`<<'TAG'` / `<<"TAG"`);
- **exact-match delimiter lines** (a line merely *starting* with the
  delimiter word is content — `ENDless` ≠ `END`);
- **lenient EOF** (an unclosed body is closed at EOF, bash-like); strictness
  lives in the scanner declining when there is NO delimiter (`cat <<` is a
  parse error — the corpus error case).

Corpus: 7 cases; both Phase-6 gotchas hit as REAL bugs during authoring:
the mid-whitespace dispatch gated on the raw lookahead (a `<` after a space
was missed — the scanner never fired), and the both-externals-valid-in-one-
state dispatch RETURNED the START decline instead of falling through to BODY
(the body was lexed as identifiers). Both are fixed in the dispatch
("try START, fall through to BODY; the source disambiguates") and pinned by
the corpus.

### 2.3 The mechanism verdict

The airtight mechanism held: both scanners went through `scanner=`,
content-addressed cache keying (scanner.c digest in the key — a stale-cache
dead-end bit the dev loop once and the reinstall fixed it), and the
`ExternalScannerRequiredError` escape hatch. The library table is now
pymini/hmini/dmini/pyindent/bashmini; both new `.c` files verified as
package data in the heavy wheel (absent from the light wheels).

**Where it leaks over real upstreams (honest):** the real Python scanner's
multi-context state (string START/CONTENT/END, format/backtick,
bracket-driven NEWLINE suppression) is a big machine; the indentation
mechanism — the part the library is for — is what's reusable, and landing
the logical-line semantics is the honest scope. The bash scanner's body
interpolation (HEREDOC_CONTENT splits, expansions) is not modeled (the
mini-grammar has plain content lines). Neither leak is a mechanism failure:
a per-language copy means "the canonical cadence + the source's
disambiguation," not "every upstream branch."

## 3. §11 re-assessed from THIS side

- **§11.2 external-scanner frequency** — the three canonical classes
  (indentation, heredoc, matched-delimiter) now have REAL mechanism copies;
  the library's value is the mechanism + the canonical cadences being
  reusable, and the "who it serves" line is the same as the ecosystem's:
  most nontrivial grammars have some scanner need, and a full replication of
  every upstream scanner is a scope correction, not the goal.
- **§11.3 toolchain packaging for B** — unchanged and re-confirmed: B's
  toolchain stays heavy-side (the light install never resolves it — Phase-6
  Run 1). The wasm probe added one fact: emcc is a real multi-hundred-MB
  build-time toolchain, and wasm does NOT remove it (it only removes the
  per-platform native compile).
- **§11.5 wasm perf** — measured, not assumed: **1.47–1.85× (median 1.6×)**
  over rust, same engine, same corpus. The note is confirmed on the high
  side of its range.

## 4. Recommendation

- **Run A: no-go for A's dependency budget** (evidence-backed: real
  artifact + real runtime + real parse + real numbers, and the binding-fork
  fact); **go-with-changes on the seam** (landed: artifact dispatch, clear
  error, env-wired real load, tests). A wasm no-go is NOT
  architecture-changing — the native bundle + per-platform wheels carry the
  distribution claim (Phase-6 verdict untouched).
- **Run B: go.** The scanner library scales to real per-language copies; the
  mechanism is reusable as pitched, and the two gotchas are now pinned by
  real-scan corpus tests, not just the seeds.
- **The single most important next step: real-user adoption — unchanged from
  Phase 6.** The consumer seam is proven, the deferred surface is now
  assessed/landed (wasm: assessed with real evidence, the seam extended; the
  scanner library: two more real copies). What the project needs is a user
  with a real grammar + a real extraction task through the light install,
  end to end. The next-deferred candidates when users ask: more per-language
  scanner copies (ruby heredocs, JS template literals, …) on the same
  mechanism, and the wasm path IF a user's platform story demands one
  artifact (the loader seam is ready for it).
