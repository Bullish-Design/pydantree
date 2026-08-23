# 021 — deep adversarial review (concept · architecture · codebase)

Independent review following 020. Attacks what the earlier reviews did not
reach: the load-bearing *claims* rather than the lines.

| file | what it is |
|---|---|
| [verdict.md](verdict.md) | the one-page answer |
| [FINDINGS.md](FINDINGS.md) | the full report: concept (C-1…C-5), architecture (A-1…A-7), defects (D-1…D-18), tests, the fix plan |
| `probes/` | seven reproduction scripts, one per attack |
| `evidence/` | captured output of every probe, plus the suite / ruff / mypy runs |

## Reproducing

```bash
# no toolchain needed
.devenv/state/venv/bin/python .scratch/projects/021-deep-adversarial-review/probes/probe_a_core.py
.devenv/state/venv/bin/python .scratch/projects/021-deep-adversarial-review/probes/probe_b_order.py
.devenv/state/venv/bin/python .scratch/projects/021-deep-adversarial-review/probes/probe_c_lists.py
.devenv/state/venv/bin/python .scratch/projects/021-deep-adversarial-review/probes/probe_f_surface.py

# needs the tree-sitter CLI + gcc (they build throwaway grammars)
devenv shell -- python .scratch/projects/021-deep-adversarial-review/probes/probe_d_toolchain.py
devenv shell -- python .scratch/projects/021-deep-adversarial-review/probes/probe_e_altpath.py
devenv shell -- python .scratch/projects/021-deep-adversarial-review/probes/probe_g_scale.py
```

## Probe map

| probe | attacks | headline result |
|---|---|---|
| `probe_a_core` | the README's own entry path, the taxonomy, the C2 honesty statement | `from_module` binds **no schema** → no checks; `_scalar_of` name-regex fallback covers 137/278 rust kinds |
| `probe_b_order` | does model field order matter? | **yes** — reversing two fields raises `Impossible pattern` (D-3) |
| `probe_c_lists` | list captures, merge, gaps, `capture_kind` | one list is correct; MISSING nodes materialize as `''` |
| `probe_d_toolchain` | two-list merge, malformed input, self-recursion, cross-language | **cartesian duplication** (D-1); `RecursionError` (D-4); cross-language returns a garbage row (D-5) |
| `probe_e_altpath` | `M()` path alternation under a bound schema | rejected as a **descent chain** (D-2); the 020 guard is vacuous (D-2b) |
| `probe_f_surface` | `__all__`, exports, `bundle_format`, `External`, ladders, extras | `import *` raises; `write_bundle` unexported; `bundle_format` versions nothing |
| `probe_g_scale` | how bad is D-1 | 12 items/field → **1728** entries/list; `n³` growth |
