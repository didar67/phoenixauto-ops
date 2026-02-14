"""
PhoenixAuto-Ops Monitoring Base

Abstract base class for all metric collectors.
Provides common functionality like threshold lookup,
error handling, and logging to ensure consistency
across CPU, Memory, Disk, and future metrics.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

from app.utils.config_loader import config
from app.utils.logger import logger


class BaseMetricCollector(ABC):
    """Base class for all system metric collectors.

    Responsibilities:
        - Load configuration thresholds
        - Centralized error handling and logging
        - Abstract interface for metric collection
    """

    def __init__(self) -> None:
        """Initialize with config and logger."""
        self.config = config
        self.logger = logger

    def get_threshold(self, metric_key: str, default: float = 80.0) -> float:
        """Safely retrieve threshold from config."""
        try:
            return self.config.get_threshold(metric_key, default)
        except Exception as e:
            self.logger.warning(f"Failed to load threshold for {metric_key}: {e}")
            return default

    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        """Collect all metrics for this collector.

        Must be implemented by subclasses.
        Returns a dictionary of metric_name -> value.
        """
        pass

    def _safe_execute(self, func, *args, **kwargs) -> Any:
        """Wrapper to safely execute metric collection functions."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Metric collection failed in {func.__name__}, error=str(e)")
            return None