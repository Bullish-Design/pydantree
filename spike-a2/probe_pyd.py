"""Probe: pydantic mechanics for model-only declarations."""
from __future__ import annotations
from typing import Annotated, Optional
from pydantic import BaseModel

# 1. does __init_subclass__ see the annotations & can we hook class creation?
class OutputModel(BaseModel):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        print(f"  [init_subclass] {cls.__name__}: annotations={dict(cls.__annotations__)}")

class M:  # path helper (placeholder)
    def __init__(self, *path, **kw): ...

def capture(field: Optional[str] = None):
    class _C:
        def __init__(s, f): s.field = f
        def __repr__(s): return f"capture({s.field!r})"
    return _C(field)

def source_meta():
    class _S: ...
    return _S()

# 2. markers as defaults + Annotated metadata
class Foo(OutputModel):
    a: str = capture("left")
    b: Annotated[int, "kind:integer", "matches:^\\d+$"] = capture()
    c: Optional[str] = None
    line: int = source_meta()

for name, f in Foo.model_fields.items():
    print(f"  field {name}: ann={f.annotation!r} metadata={list(f.metadata)!r} default={f.default!r} required={f.is_required()}")

# 3. Annotated with arbitrary marker objects (not strings)
class Matches:
    def __init__(self, re): self.re = re
class NodeKind:
    def __init__(self, kind): self.kind = kind

class Bar(OutputModel):
    name: Annotated[str, Matches(r"^[A-Z]")] = capture("left")
    value: Annotated[int, NodeKind("integer")] = capture("right")

for name, f in Bar.model_fields.items():
    print(f"  field {name}: metadata={f.metadata}")

# 4. does BaseModel forbid __init_subclass__ on subclass-of-subclass ordering? and can we read annotations in init_subclass before pydantic mangles?
class Sub(Foo):
    extra: int = capture("x")
print("  Sub fields:", list(Sub.model_fields))
