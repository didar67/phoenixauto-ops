"""
PhoenixAuto-Ops Healing Base

Abstract base class for all self-healing actions.
Provides common functionality like dry-run mode,
retry logic, and centralized logging to ensure
consistent and safe healing across the system.
"""

from abc import ABC, abstractmethod
from typing import Any
from time import sleep

from app.utils.config_loader import config
from app.utils.logger import logger


class BaseHealer(ABC):
    """Base class for all self-healing actions.

    Responsibilities:
        - Handle dry-run mode for safe testing
        - Provide retry mechanism with configurable attempts
        - Centralized logging and error handling
    """

    def __init__(self) -> None:
        """Initialize with config and logger."""
        self.config = config
        self.logger = logger
        self.healing_enabled = self.config.get("auto_healing.enabled", True)
        self.max_retries = self.config.get("auto_healing.max_retry_attempts", 3)
        self.dry_run = self.config.get("auto_healing.dry_run", True)

    def _should_heal(self) -> bool:
        """Check if healing is enabled in config."""
        if not self.healing_enabled:
            self.logger.info("Healing is disabled in config. Skipping action.")
            return False
        return True

    def _safe_execute(self, action_name: str, func, *args, **kwargs) -> Any:
        """Execute healing action with retry and error handling."""
        for attempt in range(1, self.max_retries + 1):
            try:
                if self.dry_run:
                    self.logger.info(f"[DRY-RUN] Would execute: {action_name}")
                    return True

                result = func(*args, **kwargs)
                self.logger.info(f"Healing action succeeded: {action_name}")
                return result
            except Exception as e:
                self.logger.warning(f"Attempt {attempt}/{self.max_retries} failed for {action_name}: {e}")
                if attempt == self.max_retries:
                    self.logger.error(f"All retry attempts failed for {action_name}")
                    raise
                sleep(2)  # small delay between retries

    @abstractmethod
    def heal(self, **kwargs) -> bool:
        """Abstract method to implement specific healing logic.

        Must be implemented by subclasses (restart_service, kill_process, etc.).
        """
        pass