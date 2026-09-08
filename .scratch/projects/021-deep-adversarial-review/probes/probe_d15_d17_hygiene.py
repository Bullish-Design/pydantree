"""Probe the D15 dead-code cleanup and D17 naming contract."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from pydantree_sitter.codegen import class_name
from pydantree_sitter_grammar.corpus import CorpusFailure, corpus_case
from pydantree_sitter_grammar.rules import _snake


def main() -> None:
    failure = CorpusFailure(corpus_case("x;", "expected", name="demo"), "got")
    report = {
        "d15_corpus_failure_message": {
            "signature": str(inspect.signature(failure.message)),
            "output": failure.message(),
        },
        "d17_canonical_acronym_mapping": {
            "rule_name": _snake("HTTPServer"),
            "class_name": class_name("http_server"),
            "rule_doc_declares_lossy": "not reversible" in _snake.__doc__,
            "codegen_doc_declares_separate_helpers": "separate helpers" in (
                Path(class_name.__code__.co_filename).read_text()),
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
