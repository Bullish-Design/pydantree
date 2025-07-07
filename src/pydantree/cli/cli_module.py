from __future__ import annotations

import argparse

from .generator import generate_from_node_types


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("pydantree")
    sub = p.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("gen", help="Generate typed models from node-types.json")
    gen.add_argument("node_types_json", help="Path to node-types.json file")
    gen.add_argument(
        "--out", required=True, help="Output path for generated .py module"
    )

    return p


def main() -> None:
    args = _build_arg_parser().parse_args()
    if args.cmd == "gen":
        generate_from_node_types(args.node_types_json, args.out)


if __name__ == "__main__":  # pragma: no cover
    main()
