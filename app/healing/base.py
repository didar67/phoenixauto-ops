"""
PhoenixAuto-Ops Healing Base

Abstract base class for all self-healing actions.
Provides common functionality like dry-run mode,
retry logic, per-action-type cooldown, and centralized
logging to ensure consistent and safe healing across the system.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from time import sleep
from typing import Any, Dict, Optional

from app.utils.config_loader import config
from app.utils.logger import logger


class BaseHealer(ABC):
    """Base class for all self-healing actions.

    Responsibilities:
        - Handle dry-run mode for safe testing
        - Provide retry mechanism with configurable attempts
        - Enforce a per-action-type cooldown so a persistently breaching
          metric doesn't re-trigger the same remediation every single cycle
        - Centralized logging and error handling
    """

    def __init__(self) -> None:
        """Initialize with config and logger."""
        self.config = config
        self.logger = logger
        self.healing_enabled = self.config.get("auto_healing.enabled", True)
        self.max_retries = self.config.get("auto_healing.max_retry_attempts", 3)
        self.dry_run = self.config.get("auto_healing.dry_run", True)
        self.cooldown_seconds = self.config.get("auto_healing.cooldown_seconds", 300)

        # Keyed by action *type* (e.g. "restart_service", "clear_cache"),
        # not the full dynamic action_name string - restart_service's
        # target process name changes cycle to cycle (see
        # SystemMetrics.get_top_cpu_process()), so keying by the literal
        # "restart <name>" string would let a new process name bypass the
        # cooldown entirely every time the culprit changes.
        self._last_healed: Dict[str, datetime] = {}

    def _should_heal(self) -> bool:
        """Check if healing is enabled in config."""
        if not self.healing_enabled:
            self.logger.info("Healing is disabled in config. Skipping action.")
            return False
        return True

    def _is_cooldown_over(self, cooldown_key: str) -> bool:
        """Check if the per-action-type cooldown window has elapsed."""
        last_time = self._last_healed.get(cooldown_key)
        if last_time and (datetime.now() - last_time) < timedelta(seconds=self.cooldown_seconds):
            self.logger.debug(f"Healing cooldown active for {cooldown_key}")
            return False
        return True

    def _safe_execute(
        self,
        action_name: str,
        func,
        *args,
        cooldown_key: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Execute healing action with cooldown, retry, and error handling."""
        key = cooldown_key or action_name
        if not self._is_cooldown_over(key):
            self.logger.info(
                f"Skipping {action_name} - healing cooldown active "
                f"({self.cooldown_seconds}s between repeats for this action type)"
            )
            return False

        for attempt in range(1, self.max_retries + 1):
            try:
                if self.dry_run:
                    self.logger.info(f"[DRY-RUN] Would execute: {action_name}")
                    self._last_healed[key] = datetime.now()
                    return True

                result = func(*args, **kwargs)
                self.logger.info(f"Healing action succeeded: {action_name}")
                self._last_healed[key] = datetime.now()
                return result
            except Exception as e:
                self.logger.warning(f"Attempt {attempt}/{self.max_retries} failed for {action_name}: {e}")
                if attempt == self.max_retries:
                    self.logger.error(f"All retry attempts failed for {action_name}")
                    # Cooldown applies even on exhausted failure - a
                    # structurally broken action (e.g. restart_service in
                    # a container with no systemd) would otherwise burn 3
                    # fresh retries on every single monitoring cycle.
                    self._last_healed[key] = datetime.now()
                    raise
                sleep(2)  # small delay between retries

    @abstractmethod
    def heal(self, **kwargs) -> bool:
        """Abstract method to implement specific healing logic.

        Must be implemented by subclasses (restart_service, kill_process, etc.).
        """
        pass
