"""pydantree_sitter.syntax — the third-parser seam (022 follow-up).

`agreement.py` owns the boundary between ast-grep's grammar and pydantree's.
This module owns a different boundary: between what **tree-sitter** calls
valid and what the **language itself** does.

They are not the same, and the gap is not academic:

```python
def f(a): x = 1
    return x
```

`root_node.has_error` is False. tree-sitter recovers by reparenting
`return x` to module level — out of the function — and reports a clean tree.
CPython raises `SyntaxError: unexpected indent`. Measured over
`src/pydantree_sitter/`, `has_error` accepted 19 of 19 broken rewrites.

A `SyntaxCheck` closes that gap for the languages that have a real parser to
hand. It is a plain callable:

    Callable[[str], None]        # returns on valid source, RAISES otherwise

The grammar consumer can set one explicitly. Otherwise the runtime resolves
one from `SYNTAX_CHECKS` by ast-grep language name. A
language with no entry gets None, and `pattern.py` falls back to a
structural proxy — see `Pattern.replace_all`.

Adding one is the cheapest way to make rewriting a new language safe. It
needs no grammar work, and for most languages it is a stdlib one-liner.
"""

from __future__ import annotations

import json
from collections.abc import Callable

__all__ = [
    "SYNTAX_CHECKS",
    "SyntaxCheck",
    "check_json",
    "check_python",
    "syntax_check_for",
]

SyntaxCheck = Callable[[str], None]


def check_python(source: str) -> None:
    """Raise `SyntaxError` if `source` is not valid Python.

    `compile` with `dont_inherit` so the calling module's `__future__`
    imports cannot change the verdict, and `PyCF_ONLY_AST` so nothing is
    executed and no bytecode is produced — this is a parse, not a run.
    """
    compile(source, "<pydantree-rewrite>", "exec",
            flags=__import__("ast").PyCF_ONLY_AST, dont_inherit=True)


def check_json(source: str) -> None:
    """Raise `json.JSONDecodeError` if `source` is not valid JSON."""
    json.loads(source)


# ast-grep language name -> check. Deliberately short: an entry is a promise
# that the check agrees with the grammar about what the language IS, and a
# wrong entry rejects valid rewrites. Add one only with a test.
SYNTAX_CHECKS: dict[str, SyntaxCheck] = {
    "python": check_python,
    "json": check_json,
}


def syntax_check_for(astgrep_name: str | None) -> SyntaxCheck | None:
    """The registered check for a language, or None.

    None is a normal answer, not a gap to apologise for: markdown has no
    notion of invalid source, and an authored grammar defines its own
    language. `pattern.py` reacts by tightening its structural check instead.
    """
    if astgrep_name is None:
        return None
    return SYNTAX_CHECKS.get(astgrep_name)
