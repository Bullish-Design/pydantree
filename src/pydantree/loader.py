"""Bootstrap helper that guarantees generated node‑type classes are loaded."""

from __future__ import annotations


class NodeTypesBootstrap:
    """Ensure generated NODE_MAP module is imported and registered exactly once."""

    _loaded: bool = False

    @classmethod
    def ensure(cls, module_name: str = "data.python_nodes") -> None:
        """Attempt to import *module_name* and register its NODE_MAP.

        Raises:
            RuntimeError: if the module cannot be imported or lacks NODE_MAP.
        """
        if cls._loaded:
            return  # already done
        try:
            mod = __import__(module_name)
        except ModuleNotFoundError as err:
            raise RuntimeError(
                f"Generated node‑types file '{module_name}.py' not found. "
                "Run `pydantree gen <node-types.json>` first."
            ) from err

        if not hasattr(mod, "NODE_MAP"):
            raise RuntimeError(f"Module '{module_name}' does not define NODE_MAP.")

        from .core import TSNode  # local import to avoid circular deps

        TSNode.register_subclasses(mod.NODE_MAP)
        cls._loaded = True
