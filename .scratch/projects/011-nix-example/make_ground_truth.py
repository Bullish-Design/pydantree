#!/usr/bin/env python3
"""
Phase 9 — Run 3: the fleet-inventory HAND TRUTH, written from nix semantics
BEFORE any extraction models exist (the phase convention). Every row below
was pinned by hand from the vendored fleet files (tests/fixtures/nix/fleet/);
the raw text slicing is mechanical (exact file text, no parse trees).

The contract (the same "raw node text" convention Phase 8 established):
  * packages   — every package REF as written inside a `packages = [ ... ]`
                 list literal (with `pkgs.`/`nodePackages.`/bare form kept);
                 direct list elements only (`++`-appended expressions are
                 noted separately, not extracted).
  * env        — `env.NAME = value`: name + the RAW TEXT of the value
                 expression (string quotes kept — nix keeps them in the CST).
  * scripts / tasks / enterShell / enterTest — name + the RAW TEXT of the
                 multiline string INCLUDING its `''` delimiters (a bash
                 string assignment keeps quotes; a nix multiline string
                 keeps its `''` pair — same contract).
  * switches   — every dotted attr path ending in `.enable = true`, with the
                 full dotted path reconstructed from the file's nesting.
  * line       — 1-based line of the item's first token (`exec = ''` opener
                 for scripts/tasks; the value line for env; the ref line for
                 packages; the `.enable = true` line for switches).

Writes tests/fixtures/nix/fleet/ground_truth.json (the oracle for Run 3).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

FLEET = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "nix" / "fleet"
OUT = FLEET / "ground_truth.json"


def text(name: str) -> list[str]:
    return (FLEET / name).read_text().splitlines()


def multiline_body(lines: list[str], open_line: int) -> tuple[str, int, int]:
    """The raw text of the multiline string that opens on `open_line` (1-based):
    from the opening `''` through the closing `''`, inclusive. Returns
    (raw_text, close_line, open_col). The closer is the first `''` NOT
    followed by `$` (an escaped `''${...}` is not a closer)."""
    i = open_line - 1
    opener = lines[i].find("''")
    assert opener != -1, f"no '' on line {open_line}: {lines[i]!r}"
    j = i
    while j < len(lines):
        k = lines[j].find("''")
        if k != -1 and (j != i or k != opener):
            nxt = lines[j][k + 2: k + 3]
            if nxt != "$":
                # raw text from the opener through the closer, inclusive
                parts = [lines[i][opener:]]
                for m in range(i + 1, j):
                    parts.append(lines[m])
                parts.append(lines[j][:k + 2])
                return "\n".join(parts), j + 1, k
        j += 1
    raise AssertionError(f"unterminated multiline string from line {open_line}")


def slice_raw(full: str, a: int, b: int) -> str:
    """The raw file text [a, b) — 0-based char offsets, a helper for value
    expressions that a human would copy verbatim."""
    return full[a:b]


def value_after_eq(lines: list[str], lineno: int) -> tuple[str, int]:
    """The raw text of a value expression starting on `lineno` (1-based) after
    `=`: from the first non-space char after `=` to the last non-space char
    before the line's trailing `;` (multi-line expressions: until the first
    line whose last non-space char is `;`)."""
    i = lineno - 1
    line = lines[i]
    eq = line.find("=")
    assert eq != -1, f"no = on line {lineno}: {line!r}"
    col = eq + 1
    while col < len(line) and line[col] in " \t":
        col += 1
    start = sum(len(l) + 1 for l in lines[:i]) + col
    j = i
    while j < len(lines):
        end = sum(len(l) + 1 for l in lines[:j]) + len(lines[j])
        if lines[j].rstrip().endswith(";"):
            end -= 1  # drop the ';'
            return slice_raw("".join(l + "\n" for l in lines), start, end), j + 1
        j += 1
    raise AssertionError(f"no terminating ; from line {lineno}")


def rows_for(lines, items):
    """items: list of (name, line) hand-pinned — slice bodies for strings."""
    pass


def main() -> int:
    packages: list[dict] = []
    env_rows: list[dict] = []
    scripts: list[dict] = []
    tasks: list[dict] = []
    switches: list[dict] = []
    shells: list[dict] = []
    tests: list[dict] = []

    def add(rows, **kw):
        rows.append(kw)

    # ---------------------------------------------------------------- mypi-agent
    l = text("mypi-agent.nix")
    add(packages, repo="mypi-agent", name="pkgs.secretspec", line=6)
    # no env / scripts / tasks / switches / shells

    # ------------------------------------------------------------------ pydantree
    l = text("pydantree.nix")
    add(packages, repo="pydantree", name="pkgs.git", line=11)
    add(packages, repo="pydantree", name="pkgs.tree-sitter", line=12)
    add(packages, repo="pydantree", name="pkgs.gcc", line=13)
    add(env_rows, repo="pydantree", name="env.GREET", value='"devenv"', line=5)
    body, close, col = multiline_body(l, 44)
    add(scripts, repo="pydantree", name="scripts.hello.exec", body=body, line=44)
    body, close, col = multiline_body(l, 59)
    add(tasks, repo="pydantree", name='tasks."pydantree:venv-src-pth".exec', body=body, line=59)
    body, close, col = multiline_body(l, 70)
    add(shells, repo="pydantree", kind="enterShell", body=body, line=70)
    body, close, col = multiline_body(l, 76)
    add(tests, repo="pydantree", kind="enterTest", body=body, line=76)
    # switches: languages.python.enable 20 / .venv.enable 22 / .uv.enable 24 /
    # .uv.sync.enable 26  (languages.rust.enable line 17 is COMMENTED OUT — no)
    add(switches, repo="pydantree", path="languages.python.enable", line=20)
    add(switches, repo="pydantree", path="languages.python.venv.enable", line=22)
    add(switches, repo="pydantree", path="languages.python.uv.enable", line=24)
    add(switches, repo="pydantree", path="languages.python.uv.sync.enable", line=26)

    # ------------------------------------------------------------ terminal-state
    l = text("terminal-state.nix")
    add(packages, repo="terminal-state", name="tmux", line=14)
    add(packages, repo="terminal-state", name="asciinema", line=15)
    add(packages, repo="terminal-state", name="agg", line=16)
    add(packages, repo="terminal-state", name="imagemagick", line=19)
    add(packages, repo="terminal-state", name="ghostscript", line=20)
    add(packages, repo="terminal-state", name="dejavu_fonts", line=23)
    add(packages, repo="terminal-state", name="liberation_ttf", line=24)
    add(packages, repo="terminal-state", name="source-code-pro", line=25)
    add(packages, repo="terminal-state", name="git", line=28)
    add(packages, repo="terminal-state", name="curl", line=29)
    add(packages, repo="terminal-state", name="jq", line=30)
    add(env_rows, repo="terminal-state", name="env.GREET",
        value='"terminal-state development environment"', line=6)
    add(env_rows, repo="terminal-state", name="env.TMUX_TMPDIR",
        value='"${config.env.DEVENV_ROOT}/.tmux"', line=8)
    for name, eline in (("record-terminal", 37), ("cast-to-gif", 47),
                        ("play-cast", 60), ("test", 72), ("format", 80),
                        ("lint", 90), ("build-package", 101)):
        body, close, col = multiline_body(l, eline)
        add(scripts, repo="terminal-state",
            name=f"scripts.{name}.exec", body=body, line=eline)
    add(switches, repo="terminal-state", path="languages.python.enable", line=112)
    add(switches, repo="terminal-state", path="languages.python.venv.enable", line=114)
    add(switches, repo="terminal-state", path="languages.python.uv.enable", line=115)
    body, close, col = multiline_body(l, 153)
    add(shells, repo="terminal-state", kind="enterShell", body=body, line=153)
    # tasks/services/pre-commit are COMMENTED OUT — no rows

    # ------------------------------------------------------ structured-agents-v2
    l = text("structured-agents-v2.nix")
    add(packages, repo="structured-agents-v2", name="pkgs.git", line=5)
    add(packages, repo="structured-agents-v2", name="pkgs.uv", line=6)
    add(packages, repo="structured-agents-v2", name="pkgs.zellij", line=7)
    for name, eline in (("project17-pytest-zellij", 10),
                        ("project17-json-workload-zellij", 22),
                        ("project17-prefix-cache-zellij", 83),
                        ("project17-gpu-pytest", 133),
                        ("project20-gpu-pytest", 168),
                        ("project23-gpu-contract", 202)):
        body, close, col = multiline_body(l, eline)
        add(scripts, repo="structured-agents-v2",
            name=f"scripts.{name}.exec", body=body, line=eline)
    add(switches, repo="structured-agents-v2",
        path="languages.python.enable", line=212)
    add(switches, repo="structured-agents-v2",
        path="languages.python.venv.enable", line=214)
    add(switches, repo="structured-agents-v2",
        path="languages.python.uv.enable", line=215)
    body, close, col = multiline_body(l, 218)
    add(shells, repo="structured-agents-v2", kind="enterShell", body=body, line=218)
    # no env rows

    # ------------------------------------------------------------------- fsdantic
    l = text("fsdantic.nix")
    add(packages, repo="fsdantic", name="git", line=100)
    add(packages, repo="fsdantic", name="curl", line=101)
    add(packages, repo="fsdantic", name="turso-cli", line=102)
    add(packages, repo="fsdantic", name="agentfsPackage", line=103)
    add(packages, repo="fsdantic", name="jq", line=106)
    add(packages, repo="fsdantic", name="ripgrep", line=107)
    add(packages, repo="fsdantic", name="just", line=108)
    env_lines = [("env.PROJECT_NAME", '"fsdantic"', 112),
                 ("env.AGENTFS_ENABLED", 'lib.mkDefault (envOrDefault "AGENTFS_ENABLED" "1")', 114),
                 ("env.AGENTFS_HOST", 'lib.mkDefault "127.0.0.1"', 116),
                 ("env.AGENTFS_PORT", 'lib.mkDefault "8081"', 117),
                 ("env.AGENTFS_DATA_DIR", 'lib.mkDefault "${root}/.devenv/state/agentfs"', 120),
                 ("env.AGENTFS_DB_NAME", 'lib.mkDefault "sandbox"', 122),
                 ("env.AGENTFS_LOG_LEVEL", 'lib.mkDefault "info"', 123),
                 ("env.AGENTFS_EXTRA_ARGS", 'lib.mkDefault ""', 124)]
    for name, value, eline in env_lines:
        add(env_rows, repo="fsdantic", name=name, value=value, line=eline)
    for name, eline in (("agentfs-info", 134), ("agentfs-url", 150),
                        ("agentfs-cli", 154), ("link-abs-to-repo", 158),
                        ("link-agentfs", 162), ("agentfs-session-create", 166),
                        ("agentfs-session-shell", 173),
                        ("agentfs-session-boot", 180)):
        body, close, col = multiline_body(l, eline)
        add(scripts, repo="fsdantic", name=f"scripts.{name}.exec", body=body, line=eline)
    body, close, col = multiline_body(l, 228)
    add(shells, repo="fsdantic", kind="enterShell", body=body, line=228)
    # no switches / tasks

    # -------------------------------------------------------------------- nixvim
    l = text("nixvim.nix")
    add(packages, repo="nixvim", name="neovim", line=185)
    for name, eline in (("git", 187), ("ripgrep", 188), ("fd", 189),
                        ("lua-language-server", 192), ("nil", 193),
                        ("bash-language-server", 194), ("pyright", 195),
                        ("rust-analyzer", 196), ("clang-tools", 197),
                        ("gopls", 198),
                        ("nodePackages.typescript-language-server", 199),
                        ("nodePackages.vscode-langservers-extracted", 200),
                        ("stylua", 203), ("alejandra", 204), ("ruff", 205),
                        ("prettierd", 206), ("goimports-reviser", 207),
                        ("nixfmt", 208), ("shellcheck", 211), ("statix", 212),
                        ("yamllint", 213), ("selene", 214),
                        ("golangci-lint", 215),
                        ("python3Packages.debugpy", 218),
                        ("nodePackages.markdownlint-cli2", 221)):
        add(packages, repo="nixvim", name=name, line=eline)
    body, close, col = multiline_body(l, 225)
    add(scripts, repo="nixvim", name="scripts.nv2.exec", body=body, line=225)
    body, close, col = multiline_body(l, 236)
    add(shells, repo="nixvim", kind="enterShell", body=body, line=236)
    # no env / switches / tasks

    # ---------------------------------------------------------------------- flora
    l = text("flora.nix")
    add(packages, repo="flora", name="pkgs.tailscale", line=51)
    add(packages, repo="flora", name="pkgs.docker", line=51)
    add(packages, repo="flora", name="pkgs.rsync", line=51)
    add(packages, repo="flora", name="pkgs.openssh", line=51)
    # ++ lib.optional config.flora.gpuHost llamaCpp — NOT a direct element
    # (appended expression; the `++` shape is a documented catalog note)
    # env values (raw text of the value expression):
    add(env_rows, repo="flora", name="env.LD_LIBRARY_PATH",
        value='"/run/opengl-driver/lib:" + pkgs.lib.makeLibraryPath [\n'
              '    pkgs.zlib             # libz.so.1        — numpy, pillow, torch\n'
              '    pkgs.stdenv.cc.cc.lib # libstdc++.so.6 + libgomp.so.1 — scipy / scikit-learn (OpenMP)\n'
              '    pkgs.zstd             # libzstd.so.1     — numpy / torch compressed IO\n'
              '    pkgs.libGL            # libGL.so.1 + libGLESv2.so.2 + libEGL.so.1 — opencv-python (cv2)\n'
              '                          # and mediapipe Tasks C bindings (anime-detector QC spikes)\n'
              '  ]',
        line=65)
    add(env_rows, repo="flora", name="env.CURATOR_DSN",
        value='"host=${pgHost} port=${pgPort} dbname=${curatorDbName}"', line=85)
    add(env_rows, repo="flora", name="env.CURATOR_OUTPUT_DIR",
        value='"${config.env.DEVENV_ROOT}/keepers"', line=89)
    add(switches, repo="flora", path="repoman.enable", line=42)
    add(switches, repo="flora", path="services.postgres.enable", line=77)
    add(switches, repo="flora", path="vendor.enable", line=448)
    add(switches, repo="flora", path="languages.python.enable", line=456)
    add(switches, repo="flora", path="languages.python.venv.enable", line=457)
    add(switches, repo="flora", path="languages.python.uv.enable", line=470)
    for name, eline in (("flora-curator-prompt-dataset", 111),
                        ("flora-curation-tag", 133),
                        ("flora-curation-sam", 172),
                        ("flora-browser-sam", 215),
                        ("flora-curation-layers", 247),
                        ("flora-qc-local", 290),
                        ("flora-sync-latest-runs", 297),
                        ("flora-sync-quality-control", 339),
                        ("flora-qc-heads", 364),
                        ("flora-qc-patchcore", 374),
                        ("flora-qc-viewer", 383),
                        ("flora-qc-tests-extra", 412),
                        ("flora-build-pipeline-report", 417)):
        body, close, col = multiline_body(l, eline)
        add(scripts, repo="flora", name=f"scripts.{name}.exec", body=body, line=eline)
    for name, eline in (("flora:local-preflight", 479),
                        ("flora:local-image-build", 505)):
        body, close, col = multiline_body(l, eline)
        add(tasks, repo="flora", name=f'tasks."{name}".exec', body=body, line=eline)
    # no enterShell / enterTest rows; processes (curator/studio/replicate) and
    # venv.requirements are out of the extraction scope

    gt = {
        "packages": packages,
        "env": env_rows,
        "scripts": scripts,
        "tasks": tasks,
        "switches": switches,
        "enterShell": shells,
        "enterTest": tests,
        "note": "hand truth written from nix semantics before the models; "
                "raw node text is the capture contract (env values keep their "
                "quotes; multiline string bodies keep their '' delimiters).",
    }
    OUT.write_text(json.dumps(gt, indent=2) + "\n")
    print(f"wrote {OUT}")
    for k, v in gt.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} rows")
    print(f"  total: {sum(len(v) for k, v in gt.items() if isinstance(v, list))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
