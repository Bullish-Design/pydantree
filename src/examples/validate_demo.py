#!/usr/bin/env python3
"""
validate_demo.py

Demonstrates validating arbitrary code nodes via `PydantreeAPI` and the
built‑in exception hierarchy.
"""

from pydantree import PyAssignment, PydantreeAPI

api = PydantreeAPI()


def show_validation(node, label: str) -> None:  # type: ignore[ann401]
    result = api.validate_code(node)
    print(f"{label}: valid={result.is_valid}, errors={result.errors}")


def main() -> None:
    # ✅ Valid assignment (value matches hint)
    ok_assign = PyAssignment(
        graphsitter_node=None,  # Integration pending
        variable_name="answer",
        value=42,
        type_hint="int",
    )
    show_validation(ok_assign, "OK assignment")

    # ❌ Invalid assignment (value violates type hint)
    bad_assign = PyAssignment(
        graphsitter_node=None,
        variable_name="oops",
        value="not an int",
        type_hint="int",
    )
    show_validation(bad_assign, "Bad assignment")


if __name__ == "__main__":
    main()
