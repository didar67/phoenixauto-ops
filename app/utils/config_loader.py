"""
PhoenixAuto-Ops Configuration Loader.

This module is responsible for loading and providing access to the project's
configuration. It supports:
- .env file for secrets (API tokens, email credentials, etc.)
- YAML file for structured thresholds and settings
- Dot-notation access for nested keys
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv


class ConfigLoader:
    """Central configuration manager for PhoenixAuto-Ops.

    Loads environment variables and YAML thresholds, providing safe access
    with defaults. Designed to be used as a singleton across the project.

    Usage:
        from app.utils.config_loader import config
        cpu_threshold = config.get_threshold('cpu_usage_percent')
        healing_enabled = config.get('auto_healing.enabled', False)
    """

    def __init__(
        self,
        config_dir: str = "config",
        env_file: str = ".env",
        yaml_file: str = "thresholds.yaml",
    ) -> None:
        """Initialize the config loader and load all sources.

        Args:
            config_dir: Directory where YAML config files are stored
            env_file: Path to the .env file (relative to project root)
            yaml_file: Name of the thresholds YAML file
        """
        self.config_dir = Path(config_dir)
        self.env_file = Path(env_file)
        self.yaml_file = self.config_dir / yaml_file

        self._config: Dict[str, Any] = {}
        self._env_loaded = False

        self._load_environment()
        self._load_yaml_config()

    def _load_environment(self) -> None:
        """Load variables from .env file if it exists."""
        if self.env_file.exists():
            load_dotenv(self.env_file)
            self._env_loaded = True
            print(".env file loaded successfully")
        else:
            print(".env file not found - using system environment variables only")

    def _load_yaml_config(self) -> None:
        """Load configuration from YAML file, fallback to example if missing."""
        if self.yaml_file.exists():
            with open(self.yaml_file, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
            print(f"Loaded configuration from {self.yaml_file.name}")
        else:
            example_file = self.config_dir / "thresholds.yaml.example"
            if example_file.exists():
                print(f"{self.yaml_file.name} not found - copying example template")
                import shutil
                shutil.copy(example_file, self.yaml_file)
                self._load_yaml_config()  # recursive reload
            else:
                print("No config files found - starting with empty configuration")
                self._config = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a configuration value using dot notation.

        Supports nested access like 'thresholds.cpu_usage_percent' or
        'auto_healing.enabled'.

        Args:
            key: Dot-separated key path
            default: Value to return if key is not found

        Returns:
            The configuration value or default
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def get_threshold(self, metric_key: str, default: float = 80.0) -> float:
        """Get a threshold value by its direct key name.

        First looks under 'thresholds' section, then falls back to top-level key.

        Args:
            metric_key: e.g. 'cpu_usage_percent', 'memory_usage_percent'
            default: Fallback value if not found

        Returns:
            Float threshold value
        """
        # First try: thresholds.<metric_key>
        value = self.get(f"thresholds.{metric_key}")
        if value is not None:
            return float(value)

        # Fallback: direct top-level key
        value = self.get(metric_key)
        if value is not None:
            return float(value)

        # Ultimate fallback
        return default

    def get_all(self) -> Dict[str, Any]:
        """Return the complete loaded configuration dictionary."""
        return self._config


# Singleton instance - import and use directly
config = ConfigLoader()