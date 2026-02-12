from __future__ import annotations

from pathlib import Path

from pydantree.cue_validation import _map_context


def test_map_context_with_capture_information(tmp_path: Path) -> None:
    ir_file = tmp_path / "ir.json"
    ir_file.write_text(
        '{"version":"v1","patterns":[{"pattern":"(function)","captures":[{"name":"function.name","source":{"file":"queries/highlights.scm"}}]}],"query_metadata":{"language":"python","query_type":"highlights","source_scm":"queries/highlights.scm"}}',
        encoding="utf-8",
    )

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
