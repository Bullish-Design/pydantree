# tests/fixtures/nix/fleet — the user's REAL devenv.nix configs (Phase 9)

The fleet-inventory extraction corpus: a representative subset of the user's
own `devenv.nix` fleet (52 repos under `~/Documents/Projects/*/devenv.nix`),
vendored for hermetic tests. The user owns these files; the fixture is
committed to the pydantree repo.

| fixture | source repo | devenv.nix commit | lines | why included |
|---|---|---|---|---|
| `mypi-agent.nix` | mypi-agent | `185f5b2` (2026-05-30) | 8 | the tiny case; `packages = [ pkgs.secretspec ]` |
| `pydantree.nix` | pydantree | `6dfecce` (2026-08-03) | 85 | medium; packages/env/languages dotted enables/scripts/tasks (the bash heredoc INSIDE a nix multiline string)/enterShell/enterTest |
| `flora.nix` | flora | `f6c85f36` (2026-08-04) | 526 | the large case; let-bindings, `${...}` interpolation, `''${...}` escaped interpolation, services.postgres, repoman.enable, vendor, venv.requirements multiline, scripts, tasks (heredocs), processes |
| `terminal-state.nix` | terminal-state | `80a5b64` (2026-01-02) | 192 | env with interpolation, `packages = with pkgs; [ ... ]`, many scripts, languages.python dotted enables |
| `structured-agents-v2.nix` | structured-agents-v2 | `e613ce4` (2026-08-04) | 221 | packages, scripts with `${pkgs.bash}` + escaped `''${...}` vars, languages enables, env |
| `fsdantic.nix` | fsdantic | `761bd24` (2026-02-13) | 250 | complex `let` bindings, `packages = with pkgs; [...]`, many scripts, enterShell |
| `nixvim.nix` | nixvim | `d1f93d9` (2026-03-01) | 240 | nixvim-module-flavored config (buildVimPlugin/fetchFromGitHub in `let`), packages, script, enterShell |

## Sanitization

- **`structured-agents-v2.nix` and `fsdantic.nix`**: the personal absolute
  path `/home/andrew/...` (in script `exec` strings and env defaults) is
  replaced with `/home/nixuser/...` — a same-shape string literal, so the
  parse is unaffected. Documented here; everything else is verbatim.
- Review found **no secrets** in any vendored file (no private keys, tokens,
  passwords; the `vim.env.ANTHROPIC_API_KEY = vim.fn.system("pass show …")`
  line in nixvim.nix calls the user's pass store at RUNTIME — the config
  holds no key material itself).

## Task coverage across the subset

| task | files |
|---|---|
| `packages = [ ... ]` / `with pkgs; [ ... ]` | mypi-agent, pydantree, flora, terminal-state, structured-agents-v2, fsdantic, nixvim |
| `env.KEY = value` | pydantree, flora, terminal-state, structured-agents-v2, fsdantic, nixvim |
| `scripts.<name>.exec` | pydantree, flora, terminal-state, structured-agents-v2, fsdantic, nixvim |
| `tasks.<name>.exec` | pydantree, flora (pydantree's nests a bash heredoc in a nix multiline string) |
| dotted `.enable = true` switches | pydantree (6), flora (6), terminal-state (7), structured-agents-v2 (3) |
| `enterShell` / `enterTest` | pydantree (both), fsdantic, nixvim, terminal-state, structured-agents-v2 |
| `''...''` multiline strings | all |
| `services.*` | flora (postgres) |
