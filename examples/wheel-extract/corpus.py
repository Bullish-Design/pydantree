"""A tiny, deterministic corpus for the wheel-extract example.

Committed on purpose: the example's per-step transcript oracle
(transcript.txt) is byte-for-byte derived from THIS file, so it must never
drift silently.
"""

def greet(name: str) -> str:
    return f"hello {name}"

answer = 42
flags = {"verbose": True}
