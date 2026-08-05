#!/usr/bin/env python3
"""Rebuild the three committed oracle bundles from their checked-in sources."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
HARNESS = REPO / "tests" / "test_oracles.py"


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: probe_artifact_rebuild.py OUTPUT_DIR")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)

    spec = importlib.util.spec_from_file_location("review019_oracles", HARNESS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    from pydantree_sitter_grammar.schema_tool import build_community_bundle

    build_community_bundle(module.BASH_FIXTURE, output / "bash", name="bash")
    build_community_bundle(module.NIX_FIXTURE, output / "nix", name="nix")
    subset = module._import_example("devenv-subset")
    module.build_subset_bundle(subset, output / "subset")
    print(f"rebuilt oracle bundles under {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
