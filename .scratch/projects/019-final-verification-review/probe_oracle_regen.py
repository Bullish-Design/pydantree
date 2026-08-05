#!/usr/bin/env python3
"""Regenerate Review 019 oracle JSON into a throwaway output directory."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
HARNESS = REPO / "tests" / "test_oracles.py"


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: probe_oracle_regen.py OUTPUT_DIR")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)

    spec = importlib.util.spec_from_file_location("review019_oracles", HARNESS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.ORACLES = output
    return module._generate()


if __name__ == "__main__":
    raise SystemExit(main())
