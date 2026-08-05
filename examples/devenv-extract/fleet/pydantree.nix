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
        VENV_SP="${config.env.DEVENV_STATE}/venv/lib/python3.13/site-packages"
        mkdir -p "$VENV_SP"
        cat > "$VENV_SP/_pydantree_src.pth" <<PTH
import sys; sys.path.insert(0, "${config.devenv.root}/src")
PTH
      '';
      after = [ "devenv:python:uv" ];
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
