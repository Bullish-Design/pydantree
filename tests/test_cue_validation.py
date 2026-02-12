from __future__ import annotations

from pydantree.cue_validation import _map_context


def test_map_context_with_capture_information() -> None:
    ir_data = {
        "version": "v1",
        "patterns": [
            {
                "pattern": "(function)",
                "captures": [
                    {"name": "function.name", "source": {"file": "queries/highlights.scm"}}
                ],
            }
        ],
        "query_metadata": {
            "language": "python",
            "query_type": "highlights",
            "source_scm": "queries/highlights.scm",
        },
    }

    line = "ir.json: captures[0].name: invalid value 123 (out of bound string type)"
    mapped = _map_context(line, ir_data)

    assert "capture=function.name" in mapped
    assert "scm=queries/highlights.scm" in mapped


def test_map_context_with_pattern_capture_path() -> None:
    ir_data = {
        "version": "v1",
        "patterns": [
            {
                "pattern": "(class_definition)",
                "captures": [{"name": "class.name", "source": {"file": "queries/tags.scm"}}],
            }
        ],
        "query_metadata": {
            "language": "python",
            "query_type": "tags",
            "source_scm": "queries/tags.scm",
        },
    }

    line = "ir.json: patterns[0].captures[0].name: invalid value"
    mapped = _map_context(line, ir_data)

    assert "capture=class.name" in mapped
    assert "scm=queries/tags.scm" in mapped
