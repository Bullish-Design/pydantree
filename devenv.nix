{ pkgs, lib, config, inputs, ... }:

{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  # Phase 0 spike needs the Rust tree-sitter generator (grammar.json -> parser.c)
  # and a C compiler to build parser.c into a shared library.
  packages = [
    pkgs.git
    pkgs.tree-sitter
    pkgs.gcc
  ];

  # https://devenv.sh/languages/
  # languages.rust.enable = true;
  languages = {
      python = {
          enable = true;
          version = "3.13";
          venv.enable = true;
          uv = {
              enable = true;
              sync = {
                  enable = true;
                  # install the root project + the dev/python extras (pytest,
                  # ruff, mypy, black, coverage, tree-sitter-json, -python)
                  allExtras = true;
                  # devenv's default args are kept: `--frozen` (uv.lock is the
                  # source of truth — run `uv lock` after dep changes) and
                  # `--no-install-workspace` (the src/* members are NOT copied
                  # into the venv — they resolve straight from src/ via the
                  # `pydantree:venv-src-pth` task below, so there is never a
                  # stale editable copy to confuse imports).
              };
            };
        };
    };
  # https://devenv.sh/processes/
  # processes.cargo-watch.exec = "cargo-watch";

  # https://devenv.sh/scripts/
  scripts.hello.exec = ''
    echo hello from $GREET
  '';

  # https://devenv.sh/tasks/
  tasks = {
    # Fresh-worktree dependency guard (REVIEW 019 V3). devenv's own
    # `devenv:python:uv` syncs ONLY the root project (uv 0.6.x `uv sync`
    # defaults to the root; the workspace members `src/pydantree_sitter` and
    # `src/pydantree_sitter_grammar` — and with them pydantic + tree-sitter —
    # are excluded unless `--all-packages` is given). In a brand-new worktree
    # the task can therefore report success while the venv cannot import the
    # locked deps. This guard validates the ACTUAL venv and, when the import
    # check fails, runs the same locked sync explicitly against that exact
    # venv with `--all-packages` so the member dependencies land. `--frozen`
    # keeps uv.lock authoritative; `--no-install-workspace` keeps the member
    # packages OUT of the venv (they resolve from src/ via the
    # `pydantree:venv-src-pth` task below — no editable copies).
    "pydantree:ensure-uv-sync" = {
      description = "Guarantee the managed venv holds the locked dependencies (fresh-worktree guard)";
      after = [ "devenv:python:uv" ];
      exec = ''
        VENV="${config.env.DEVENV_STATE}/venv"
        PY="$VENV/bin/python"

        check_imports() {
          "$PY" -c 'import pydantic, pytest, tree_sitter' >/dev/null 2>&1
        }

        if check_imports; then
          echo "pydantree: venv imports OK (pydantic, pytest, tree_sitter)"
          exit 0
        fi

        echo "pydantree: venv missing locked deps — running uv sync --all-packages" >&2
        if ! (cd "${config.devenv.root}" && \
            UV_PROJECT_ENVIRONMENT="$VENV" \
            uv sync --all-extras --frozen --no-install-workspace --all-packages); then
          echo "pydantree: uv sync failed — run 'uv sync --all-extras --frozen' manually" >&2
          exit 1
        fi

        if check_imports; then
          echo "pydantree: venv synced and imports OK (pydantic, pytest, tree_sitter)"
        else
          echo "pydantree: venv STILL cannot import pydantic/pytest/tree_sitter after sync" >&2
          exit 1
        fi
      '';
    };

    # The editable-staleness fix (Phase-8 dev-flow hardening): write a .pth
    # into the managed venv that puts the repo's `src/` FIRST on sys.path.
    # A .pth line starting with `import` runs during site-packages processing,
    # so the insert lands before site-packages — every process using this venv
    # (tests, probes, `python -c`) resolves pydantree_sitter / pydantree_sitter_grammar straight
    # from src/. No editable copies -> no stale-copy surprises. Runs after the
    # venv is (re)created, idempotently.
    "pydantree:venv-src-pth" = {
      description = "Point the venv at the repo's src/ (editable-copy staleness fix)";
      exec = ''
        VENV_SP="$(echo "${config.env.DEVENV_STATE}"/venv/lib/python*/site-packages)"
        mkdir -p "$VENV_SP"
        cat > "$VENV_SP/_pydantree_src.pth" <<PTH
import sys; sys.path.insert(0, "${config.devenv.root}/src")
PTH
      '';
      after = [ "pydantree:ensure-uv-sync" ];
    };
  };

  enterShell = ''
    hello
    git --version
  '';

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';

  # https://devenv.sh/git-hooks/
  # git-hooks.hooks.shellcheck.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
