# wheel-extract — Product A over a community wheel, NO toolchain

The **toolchain-free** example (Review 020's headline recommendation): a
community grammar **wheel** (`tree-sitter-python` — no tree-sitter CLI, no
gcc, no bundle build) drives the whole Product A surface, and **every step
lands in a committed per-step transcript oracle** so a reader sees exactly
what is being done at each step — and a test proves the example still
produces that exact output.

What each step shows:

| step | what you see |
|---|---|
| **1. bind** | the two models and the `.scm` each class *is* (`compiled_source()`) — the derived query, no grammar build anywhere |
| **2. parse** | the corpus's CST with field names (`name=`, `return_type=`, `left=`, …) |
| **3. extract** | the typed rows: `Function 'greet' -> 'str' at line 8`, `Assignment 'answer' = '42' at line 11` |
| **4. self-check** | rows vs the hand-written `ground_truth.json` |
| **5. transcript oracle** | this run's output vs the committed `transcript.txt`, byte-for-byte |

Run it (any env with `pydantree_sitter` + `tree-sitter-python` installed —
no toolchain):

```bash
python examples/wheel-extract/extract.py             # run + self-check
python examples/wheel-extract/extract.py --update    # regenerate transcript.txt
```

Changing the corpus, the models, or extraction behavior will make step 5
report a **drift** (exit 1) — regenerate with `--update`, eyeball the diff,
commit. `tests/test_wheel_example.py` runs the example as a subprocess and
asserts `stdout == transcript.txt` (and that the transcript really shows
each step), so the oracle cannot rot silently.

Contrast with the other examples: `bash-extract` and `devenv-extract` run
over real grammar *sources* (they need the toolchain at build time) and
`devenv-subset` authors a grammar from scratch. This one needs **nothing** —
it is the lightest possible entry point.
