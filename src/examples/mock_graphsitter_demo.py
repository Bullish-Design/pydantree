#!/usr/bin/env python3
"""
mock_graphsitter_demo.py

Shows how to wrap an existing (mock) GraphSitter node with Pydantree
models so you can leverage validation and high‑level helpers without
using the builder APIs.
"""

from pydantree import PyClass


class MockGraphSitterNode:
    """Tiny stub mimicking the minimal interface Pydantree expects."""

    def __init__(self, source: str, node_type: str = "PyClass"):
        self._source = source
        self.type = node_type  # heuristic used by utils.factory.from_graphsitter

    # Pydantree relies on these two methods for integration
    def to_source(self) -> str:  # noqa: D401
        return self._source

    def validate_structure(self) -> bool:  # noqa: D401
        return True  # Pretend our node is always structurally sound


def main() -> None:
    # Pretend we parsed this code with GraphSitter
    raw_src = "class Service:\n    pass\n"
    gs_node = MockGraphSitterNode(raw_src, node_type="PyClass")

    # Wrap it – no builders needed
    # Wrap it – supply the required class_name that Pydantree doesn’t yet
    # auto‑extract from the GraphSitter node.
    # service_cls = PyClass(graphsitter_node=gs_node, class_name="Service")

    print("Original source from GraphSitter:")
    print(gs_node.to_source())

    service_cls = PyClass.from_graphsitter(gs_node)
    # Mutate using Pydantree helpers
    service_cls.add_method("ping", return_type="str")

    print("\nAfter modification:")
    print(service_cls.to_class_definition())
    for m in service_cls.methods:
        print("  ", m.to_signature())


if __name__ == "__main__":
    main()
