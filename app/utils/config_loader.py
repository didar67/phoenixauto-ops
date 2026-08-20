"""
PhoenixAuto-Ops Configuration Loader.

This module is responsible for loading and providing access to the project's
configuration. It supports:
- .env file for secrets (API tokens, email credentials, etc.)
- YAML file for structured thresholds and settings
- Dot-notation access for nested keys
"""

import shutil
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

from app.utils.logger import logger


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
        try:
            if self.env_file.exists():
                load_dotenv(self.env_file)
                self._env_loaded = True
                logger.info(".env file loaded successfully")
            else:
                logger.warning(".env file not found - using system environment variables only")
        except Exception as e:
            logger.error(f"Failed to load .env file: {e}")

    def _load_yaml_config(self, is_retry: bool = False) -> None:
        """Load configuration from YAML file, fallback to example if missing."""
        if self.yaml_file.exists():
            try:
                with open(self.yaml_file, "r", encoding="utf-8") as f:
                    loaded_data = yaml.safe_load(f)
                    if isinstance(loaded_data, dict):
                        self._config = loaded_data
                        logger.info(f"Loaded configuration from {self.yaml_file.name}")
                    else:
                        logger.error(
                            f"YAML config {self.yaml_file.name} is not a valid dictionary. Starting with empty config."
                        )
                        self._config = {}
            except yaml.YAMLError as e:
                logger.error(f"YAML parsing error in {self.yaml_file.name}: {e}")
                self._config = {}
            except (PermissionError, OSError) as e:
                logger.error(f"IO error reading {self.yaml_file.name}: {e}")
                self._config = {}
            except Exception as e:
                logger.error(f"Unexpected error loading {self.yaml_file.name}: {e}")
                self._config = {}
        else:
            example_file = self.config_dir / "thresholds.yaml.example"
            if example_file.exists() and not is_retry:
                logger.warning(
                    f"{self.yaml_file.name} not found - copying example template from {example_file.name}"
                )
                try:
                    self.config_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy(example_file, self.yaml_file)
                    self._load_yaml_config(is_retry=True)  # Safe recursive reload
                except (PermissionError, OSError) as e:
                    logger.error(f"Failed to copy example config file: {e}")
                    self._config = {}
            else:
                logger.warning("No config files found - starting with empty configuration")
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
        if not isinstance(key, str) or not key:
            logger.error(f"Invalid key provided to get(): {key}")
            return default

        keys = key.split(".")
        value = self._config

        try:
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value
        except Exception as e:
            logger.error(f"Unexpected error retrieving config key '{key}': {e}")
            return default

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

        # Fallback: direct top-level key
        if value is None:
            value = self.get(metric_key)

        if value is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid non-numeric threshold value '{value}' for key "
                    f"'{metric_key}'. Falling back to default {default}"
                )

        # Ultimate fallback
        return default

    def get_all(self) -> Dict[str, Any]:
        """Return the complete loaded configuration dictionary."""
        return self._config


# Singleton instance - import and use directly
config = ConfigLoader()
