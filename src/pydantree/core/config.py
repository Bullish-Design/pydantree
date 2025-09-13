# pydantree/core/config.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ConfigDict
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Centralized configuration for Pydantree."""
    
    # Core settings
    cache_enabled: bool = Field(default=True, description="Enable caching")
    cache_dir: Path = Field(default_factory=lambda: Path.home() / ".pydantree" / "cache")
    max_cache_size_mb: int = Field(default=1024, description="Maximum cache size in MB")
    
    # Performance settings
    default_workers: int = Field(default_factory=lambda: min(32, (os.cpu_count() or 1) + 4))
    batch_size: int = Field(default=100, description="Default batch size for processing")
    parser_pool_size: int = Field(default=10, description="Parsers per language")
    
    # Profiling settings
    profiling_enabled: bool = Field(default=False)
    memory_tracking: bool = Field(default=True)
    max_profile_history: int = Field(default=10000)
    
    # Language settings
    auto_detect_language: bool = Field(default=True)
    fallback_language: Optional[str] = Field(default=None)
    supported_languages: List[str] = Field(default_factory=lambda: ["python"])
    
    # Export settings
    default_export_format: str = Field(default="json")
    compression_enabled: bool = Field(default=False)
    streaming_threshold_mb: int = Field(default=100)
    
    # Logging settings
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Development settings
    debug_mode: bool = Field(default=False)
    strict_mode: bool = Field(default=True, description="Strict error handling")
    
    model_config = ConfigDict(env_prefix="PYDANTREE_", case_sensitive=False)
    #class Config:
    #    env_prefix = "PYDANTREE_"
    #    case_sensitive = False


def get_default_config() -> Config:
    """Get default configuration with environment overrides."""
    return Config()


def get_config_from_file(config_path: Path) -> Config:
    """Load configuration from file."""
    if config_path.suffix == ".json":
        import json
        with config_path.open() as f:
            data = json.load(f)
        return Config(**data)
    elif config_path.suffix in [".yml", ".yaml"]:
        import yaml
        with config_path.open() as f:
            data = yaml.safe_load(f)
        return Config(**data)
    else:
        raise ValueError(f"Unsupported config file format: {config_path.suffix}")


def get_config() -> Config:
    """Get configuration with automatic discovery."""
    # Check for config file in standard locations
    config_locations = [
        Path("pydantree.json"),
        Path("pyproject.toml"),  # TODO: Support TOML
        Path.home() / ".pydantree" / "config.json",
    ]
    
    for config_path in config_locations:
        if config_path.exists():
            try:
                return get_config_from_file(config_path)
            except Exception:
                continue  # Try next location
    
    return get_default_config()
