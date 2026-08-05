from typing import Annotated
from pydantic import BaseModel

class OutputModel(BaseModel):
    _derived = {}
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        try:
            fields = list(cls.model_fields)
            print(f"  [init_subclass] {cls.__name__}: model_fields available -> {fields}")
        except Exception as e:
            print(f"  [init_subclass] {cls.__name__}: model_fields NOT available ({type(e).__name__}: {e})")

class Foo(OutputModel):
    a: str
    b: int

# is it available after the class is created, i.e. can a metaclass do it?
import pydantic
class DerivingMeta(pydantic._internal._model_construction.ModelMetaclass):
    def __new__(mcls, name, bases, ns, **kw):
        cls = super().__new__(mcls, name, bases, ns, **kw)
        print(f"  [meta __new__] {name}: model_fields={list(cls.model_fields)}")
        return cls

class Bar(BaseModel, metaclass=DerivingMeta):
    x: int

print("  done")
