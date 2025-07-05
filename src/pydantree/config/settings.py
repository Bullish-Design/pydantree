from __future__ import annotations

from confidantic import SettingsType, PluginRegistry
from pydantic import Field


class PydantreeConfig(SettingsType):
    """Configuration options and defaults for Pydantree."""
    
    validation_strict: bool = Field(
        default=True, 
        env="PYDANTREE_VALIDATION_STRICT",
        description="Enable strict validation"
    )
    allow_partial_types: bool = Field(
        default=False, 
        env="PYDANTREE_ALLOW_PARTIAL_TYPES",
        description="Allow incomplete type annotations"
    )
    auto_format_code: bool = Field(
        default=True, 
        env="PYDANTREE_AUTO_FORMAT",
        description="Automatically format generated code"
    )
    max_complexity: int = Field(
        default=10, 
        env="PYDANTREE_MAX_COMPLEXITY",
        description="Maximum allowed cyclomatic complexity"
    )


# Register with Confidantic
PluginRegistry.register(PydantreeConfig)
