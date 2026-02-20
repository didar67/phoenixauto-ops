"""
PhoenixAuto-Ops Alerting Base

Abstract base class for all alert senders.
Provides common functionality like message formatting,
cooldown checks, and error handling to ensure consistency
across Telegram, Email, Slack, and future channels.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from datetime import datetime, timedelta

from app.utils.config_loader import config
from app.utils.logger import logger


class BaseAlertSender(ABC):
    """Base class for all alerting channels.

    Responsibilities:
        - Format alert messages uniformly
        - Handle cooldown to prevent alert spam
        - Centralized error handling and logging
    """

    def __init__(self) -> None:
        """Initialize with config and logger."""
        self.config = config
        self.logger = logger
        self.cooldown_minutes = self.config.get("alerting.cooldown_minutes", 15)
        self.last_sent: Dict[str, datetime] = {}  # Metric key -> last alert time

    def _is_cooldown_over(self, metric_key: str) -> bool:
        """Check if cooldown period has passed for this metric."""
        last_time = self.last_sent.get(metric_key)
        if last_time and (datetime.now() - last_time) < timedelta(minutes=self.cooldown_minutes):
            self.logger.debug(f"Cooldown active for {metric_key}")
            return False
        return True

    def _format_message(self, metric: str, value: float, threshold: float, level: str) -> str:
        """Format a standard alert message."""
        return f"{level.upper()} Alert: {metric} exceeded threshold ({value} > {threshold})"

    def send_alert(self, metric: str, value: float, threshold: float, level: str = "warning") -> bool:
        """Public method to send an alert with cooldown and error handling."""
        try:
            if not self._is_cooldown_over(metric):
                return False
            message = self._format_message(metric, value, threshold, level)
            self._send(message)
            self.last_sent[metric] = datetime.now()
            self.logger.info(f"Alert sent for {metric}: {message}", level=level)
            return True
        except Exception as e:
            self.logger.error(f"Failed to send alert for {metric}: {e}")
            return False

    @abstractmethod
    def _send(self, message: str) -> None:
        """Abstract method to implement channel-specific sending logic.

        Must be implemented by subclasses (e.g., Telegram, Email).
        """
        pass