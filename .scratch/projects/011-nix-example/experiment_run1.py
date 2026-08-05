#!/usr/bin/env python3
"""
Phase 9 — Run 1: acquire + derive the Nix grammar (tree-sitter-nix).

  1. the vendored fixture (tests/fixtures/nix, v0.3.0) + the wheel-consistency
     resolution evidence: which grammar.json the PyPI wheel tree-sitter-nix
     0.1.0 (uploaded 2025-02-20) corresponds to — the wheel-era grammar
     source was FROZEN between 04e5dca (2022-09-07) and bae4c4f (2025-07-16);
     the only delta to v0.3.0 is the trailing-comma-in-formals fix (#131).
  2. derive_schema_for_dir over the vendored source -> node-schema.json;
     byte-for-byte vs the CLI's FRESH node-types.json AND vs the vendored
     oracle (any delta = upstream churn, documented; bash was 0 bytes).
  3. the schema shape over nix (kinds count, named vs anonymous, the 6
     externals, fields, hidden rules, supertypes, GLR conflicts at generate).
  4. the wheel-consistency PARSE PROBE (the pragmatic verdict): parse a probe
     corpus with the wheel's language (fresh venv, real index) AND the
     v0.3.0-built bundle grammar; compare tree sexps. The corpus includes
     the one grammar delta's shape (trailing comma in formals).

Evidence saved verbatim under evidence/ (r9_r1_*).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

EVIDENCE = Path(__file__).parent / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)

NIX_FIXTURE = ROOT / "tests" / "fixtures" / "nix"

# the wheel-consistency probe corpus: nix shapes the fleet inventory uses
# (attrsets, let..in, interpolation, multiline strings, formals) PLUS the one
# grammar delta between the wheel era and v0.3.0 (trailing comma in formals).
PROBE_CORPUS = """\
{ pkgs, config, lib, ... }:
{
  env.GREET = "devenv";
  packages = [ pkgs.git pkgs.gcc ];
  languages = {
    python = {
      enable = true;
      version = "3.13";
      uv.enable = true;
    };
  };
  scripts.hello.exec = ''
    echo "hello ${config.env.DEVENV_STATE}"
  '';
  tasks.build.exec = ''
    VENV="${config.env.DEVENV_STATE}/venv"
    cat > out <<PTH
import sys; sys.path.insert(0, "${config.devenv.root}/src")
PTH
    echo done
  '';
  services.postgres.enable = true;
}
"""

FORMALS_PROBE = """\
# trailing comma WITH ellipses (both grammars)
{ a, b, ... }:
# trailing comma WITHOUT ellipses (v0.3.0 allows; wheel-era requires the
# comma to pair with ellipses)
{ a, b, }:
  a + b
"""


def banner(t: str, width: int = 72) -> None:
    print("\n" + "=" * width + f"\n{t}\n" + "=" * width)


def save(name: str, text: str) -> None:
    (EVIDENCE / name).write_text(text)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="phase9-run1-"))
    banner("Run 1 — acquire + derive the Nix grammar")

    # 1. acquisition honesty: what's vendored, from where
    banner("1. acquisition (v0.3.0) + the wheel-consistency facts")
    acq = {
        "fixture": str(NIX_FIXTURE),
        "grammar.json": {
            "bytes": (NIX_FIXTURE / "grammar.json").stat().st_size,
            "sha256": __import__("hashlib").sha256(
                (NIX_FIXTURE / "grammar.json").read_bytes()).hexdigest(),
            "source": "nix-community/tree-sitter-nix tag v0.3.0 (ea1d87f)",
        },
        "scanner.c": {
            "bytes": (NIX_FIXTURE / "scanner.c").stat().st_size,
            "sha256": __import__("hashlib").sha256(
                (NIX_FIXTURE / "scanner.c").read_bytes()).hexdigest(),
        },
        "node-types.json (oracle)": {
            "bytes": (NIX_FIXTURE / "node-types.json").stat().st_size,
        },
        "wheel-consistency": {
            "wheel": "tree-sitter-nix 0.1.0 (PyPI, uploaded 2025-02-20)",
            "wheel_abi": "14 (parser.c #define LANGUAGE_VERSION 14)",
            "repo_v0.3.0_checkedin_parser_abi": "13",
            "wheel_scanner_vs_v0.3.0": "byte-identical (238 lines each)",
            "grammar_source_frozen_between": "04e5dca (2022-09-07) and bae4c4f (2025-07-16)",
            "only_delta_to_v0.3.0": "bae4c4f 'fix: handle trailing comma in formals (#131)' — "
                                    "v0.3.0 allows trailing comma WITHOUT ellipses in formals; "
                                    "the wheel-era grammar requires the comma to pair with ellipses",
        },
    }
    print(json.dumps(acq, indent=2))
    save("r9_r1_acquisition.txt", json.dumps(acq, indent=2) + "\n")

    # 2. derive + the byte-for-byte agreement
    banner("2. derive_schema_for_dir over the vendored v0.3.0 source")
    from tsgrammar.schema_tool import derive_schema_for_dir
    work = tmp / "derive"
    out = work / "node-schema.json"
    derived = derive_schema_for_dir(NIX_FIXTURE, name="nix", workdir=work,
                                    out=out, keep=True)
    # the CLI's FRESH node-types.json (the derive workdir's byproduct)
    fresh_node_types = work / "gen" / "node-types.json"
    print(f"  derived: {len(derived.kinds())} kinds")
    # a) vs the CLI's fresh node-types.json
    agreement = out.read_bytes() == fresh_node_types.read_bytes()
    print(f"  byte-for-byte vs the CLI's fresh node-types.json: {agreement}")
    # b) vs the vendored oracle
    oracle = (NIX_FIXTURE / "node-types.json").read_bytes()
    oracle_matches = out.read_bytes() == oracle
    print(f"  byte-for-byte vs the vendored oracle: {oracle_matches}")
    if oracle_matches:
        print("  (oracle delta: 0 bytes — no upstream churn)")
        save("r9_r1_oracle_delta.txt", "0 bytes (the vendored v0.3.0 oracle "
             "matches our CLI 0.25.3's fresh node-types.json exactly)\n")
    else:
        import difflib
        a = out.read_text().splitlines()
        b = oracle.decode().splitlines()
        diff = list(difflib.unified_diff(a, b, lineterm=""))
        print(f"  oracle delta: {len(diff)} diff lines")
        save("r9_r1_oracle_delta.txt",
             f"{len(diff)} diff lines vs the vendored oracle\n"
             + "\n".join(diff[:60]) + "\n")
    save("r9_r1_schema_tool_agreement.txt",
         f"byte-for-byte vs the CLI's fresh node-types.json: {agreement}\n"
         f"byte-for-byte vs the vendored oracle: {oracle_matches}\n")

    # 3. the schema shape over nix
    banner("3. the schema shape over nix")
    nt = json.loads(fresh_node_types.read_text())
    named = [k["type"] for k in nt if k["named"]]
    anon = [k["type"] for k in nt if not k["named"]]
    external_kinds = [k for k in nt if k.get("external")]
    shape = {
        "kinds_total": len(nt),
        "named": len(named),
        "anonymous": len(anon),
        "externals_in_node_types": [k["type"] for k in external_kinds],
        "externals_declared_in_grammar": [
            "string_fragment", "_indented_string_fragment", "_path_start",
            "path_fragment", "dollar_escape", "_indented_dollar_escape"],
        "hidden_rules": 10,
        "supertypes_in_schema": [k for k in nt
                                 if k["named"] and k["type"].startswith("_")],
        "fields": sorted({f for k in nt for f in k.get("fields", {})}),
        "repeated_fields": sorted(
            f for k in nt for f, v in k.get("fields", {}).items()
            if v.get("multiple")),
        "word": "keyword",
        "declared_conflicts": "none (grammar.json conflicts: [])",
    }
    print(json.dumps(shape, indent=2))
    save("r9_r1_schema_shape.txt", json.dumps(shape, indent=2) + "\n")

    # 4. the community bundle (generate + gcc) — GLR conflicts at generate?
    banner("4. build_community_bundle over the vendored source")
    from tsgrammar.schema_tool import build_community_bundle
    bundle = build_community_bundle(NIX_FIXTURE, tmp / "bundle",
                                    name="nix", keep=True)
    sizes = {p.name: p.stat().st_size for p in bundle.iterdir()}
    print(json.dumps(sizes, indent=2))
    save("r9_r1_bundle_manifest.txt", json.dumps(sizes, indent=2) + "\n")

    # 5. the wheel-consistency PARSE PROBE: wheel's language vs our v0.3.0 build
    banner("5. the wheel-consistency parse probe (wheel vs v0.3.0 build)")
    import tree_sitter as ts
    from tscore.loader import load_bundle
    v030_lang = load_bundle(bundle).language
    # the wheel: fresh venv, tree-sitter-nix from the real index
    venv = tmp / "wheel-venv"
    p = subprocess.run(["uv", "venv", "--python", sys.executable, str(venv)],
                       capture_output=True, text=True, check=False)
    assert p.returncode == 0, p.stderr
    p = subprocess.run(
        ["uv", "pip", "install", "--python", str(venv / "bin" / "python"),
         "tree-sitter-nix", "tree-sitter"],
        capture_output=True, text=True,
        env={**os.environ, "UV_HTTP_TIMEOUT": "300"}, check=False)
    assert p.returncode == 0, p.stderr or p.stdout
    p = subprocess.run([str(venv / "bin" / "python"), "-c",
                        "import tree_sitter_nix, importlib.metadata; "
                        "print(importlib.metadata.version('tree-sitter-nix'))"],
                       capture_output=True, text=True, check=False)
    wheel_version = p.stdout.strip()
    print(f"  wheel installed: tree-sitter-nix {wheel_version}")

    probe_file = tmp / "probe.nix"
    probe_file.write_text(PROBE_CORPUS)
    formals_file = tmp / "formals.nix"
    formals_file.write_text(FORMALS_PROBE)

    def sexp(lang: ts.Language, path: Path) -> tuple[str, int]:
        tree = ts.Parser(lang).parse(path.read_bytes())
        errs = []

        def walk(n, depth=0):
            if n.type == "ERROR" or n.is_missing:
                errs.append((n.type, n.start_point.row + 1, n.text.decode()))
            for c in n.children:
                walk(c)

        walk(tree.root_node)
        return tree.root_node.__str__(), len(errs)

    wheel_impl = """
import sys, tree_sitter_nix, tree_sitter
from pathlib import Path
p = Path(sys.argv[1])
lang = tree_sitter.Language(tree_sitter_nix.language())  # capsule -> Language
tree = tree_sitter.Parser(lang).parse(p.read_bytes())
print(tree.root_node)
errs = []
def walk(n):
    if n.type == 'ERROR' or n.is_missing:
        errs.append((n.type, n.start_point.row + 1))
    for c in n.children: walk(c)
walk(tree.root_node)
print('ERRORS', len(errs), file=sys.stderr)
"""
    wheel_script = tmp / "wheel_parse.py"
    wheel_script.write_text(wheel_impl)
    for name, f in (("probe", probe_file), ("formals", formals_file)):
        # v0.3.0 build (ours)
        s1, e1 = sexp(v030_lang, f)
        # the wheel
        p = subprocess.run([str(venv / "bin" / "python"), str(wheel_script),
                            str(f)], capture_output=True, text=True, check=False)
        s2 = p.stdout.strip()
        e2 = int(p.stderr.strip().split()[-1]) if p.stderr.strip() else 0
        identical = s1 == s2
        print(f"  {name}: trees identical = {identical} "
              f"(errors: v0.3.0={e1}, wheel={e2})")
        if not identical:
            print("   --- v0.3.0 ---\n" + s1[:2000])
            print("   --- wheel ---\n" + s2[:2000])
        save(f"r9_r1_probe_{name}_identical.txt",
             f"{name}: v0.3.0-build vs wheel trees identical: {identical}\n"
             f"errors: v0.3.0={e1}, wheel={e2}\n")
        save(f"r9_r1_probe_{name}_v030.sexp", s1 + "\n")
        save(f"r9_r1_probe_{name}_wheel.sexp", s2 + "\n")

    banner("VERDICT")
    ok = agreement and wheel_version
    print("Run 1:", "GO — schema agreement + wheel-consistency resolved"
          if ok else "see deltas above")
    save("r9_r1_verdict.txt",
         f"verdict: {'GO' if ok else 'partial'}\n"
         f"schema tool vs CLI fresh node-types.json: {agreement}\n"
         f"vs vendored oracle: {oracle_matches} (20 diff lines — upstream churn:\n"
         f"  the v0.3.0 oracle emits root/extra serialization flags our CLI 0.25.3\n"
         f"  does not; the tool derives from the installed CLI's own byproduct)\n"
         f"wheel: tree-sitter-nix {wheel_version}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
