"""
PhoenixAuto-Ops System Metrics Collector

Collects core system health metrics using psutil:
- CPU usage (%)
- Memory usage (%)
- Disk usage (%)
- Load average

Inherits from BaseMetricCollector for consistent
error handling, logging, and threshold access.
"""

import psutil
import os
from typing import Dict, Any, Optional

from app.monitoring.base import BaseMetricCollector
from app.utils.logger import logger

# In containerized host-monitoring mode, docker-compose bind-mounts the
# host's /proc into /host/proc and sets HOST_PROC_PATH. Pointing psutil at
# it here - once, at import time - is what actually makes cpu/memory/network
# numbers reflect the host instead of the container's own namespace; without
# this, psutil silently falls back to the container's default /proc and every
# metric below would describe the container, not the machine it runs on.
# Left unset for bare-metal/dev runs, where the default /proc is already
# the right one.
_HOST_PROC_PATH = os.environ.get("HOST_PROC_PATH")
if _HOST_PROC_PATH:
    psutil.PROCFS_PATH = _HOST_PROC_PATH
    logger.info(f"Host monitoring mode enabled (PROCFS_PATH={_HOST_PROC_PATH})")

class SystemMetrics(BaseMetricCollector):
    """Concrete collector for core system metrics.

    Uses psutil to gather real-time system data.
    Applies thresholds from config to determine health status.
    """

    def collect(self) -> Dict[str, Any]:
        """Collect all system metrics in one call.

        Returns:
            Dict containing cpu, memory, disk, and load metrics.
        """
        self.logger.debug("Starting system metrics collection")

        metrics = {
            "cpu_usage_percent": self._safe_execute(self._get_cpu_usage),
            "memory_usage_percent": self._safe_execute(self._get_memory_usage),
            "disk_usage_percent": self._safe_execute(self._get_disk_usage),
            "load_average": self._safe_execute(self._get_load_average),
        }

        self.logger.info(f"System metrics collected", **metrics)
        return metrics

    def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage (1-second interval)."""
        return psutil.cpu_percent(interval=1)

    def _get_memory_usage(self) -> float:
        """Get memory usage as percentage of total RAM."""
        return psutil.virtual_memory().percent

    def _get_disk_usage(self) -> float:
        """Get root filesystem disk usage percentage."""
        return psutil.disk_usage("/").percent

    def _get_load_average(self) -> float:
        """Get 1-minute system load average."""
        return psutil.getloadavg()[0]

    def is_healthy(self, metrics: Optional[Dict[str, Any]] = None) -> bool:
        """Check if all metrics are below warning thresholds.
        Args:
            metrics: Already-collected metrics dict from this same cycle.
                Pass this whenever the caller already has fresh data so we
                don't pay for a second psutil pass (and, since network
                collection sleeps for I/O deltas, don't double that cost
                either). Falls back to collecting fresh data if omitted,
                so this stays a drop-in call on its own.
        """
        if metrics is None:
            metrics = self.collect()

        cpu_ok = metrics["cpu_usage_percent"] < self.get_threshold("cpu_usage_percent")
        mem_ok = metrics["memory_usage_percent"] < self.get_threshold("memory_usage_percent")

        disk_ok = metrics["disk_usage_percent"] < self.get_threshold("disk_usage_percent")
        load_ok = metrics["load_average"] < self.get_threshold("load_average_limit")

        return cpu_ok and mem_ok and disk_ok and load_ok