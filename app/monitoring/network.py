"""
PhoenixAuto-Ops Network Metrics Collector

Collects network-related system metrics using psutil:
- Bytes sent/received (per second)
- Active TCP connections
- Optional: simple latency check (future)

Inherits from BaseMetricCollector for consistent
threshold handling, logging, and error safety.
"""

import time
from typing import Dict, Any, Optional

import psutil

from app.monitoring.base import BaseMetricCollector


class NetworkMetrics(BaseMetricCollector):
    """Concrete collector for network health metrics.

    Focuses on bandwidth usage and connection count.
    Designed to be lightweight and production-safe.
    """

    def collect(self) -> Dict[str, Any]:
        """Collect all network metrics in one call.

        Returns:
            Dict with network_io and connections data.
        """
        self.logger.debug("Starting network metrics collection")

        metrics = {
            "network_bytes_sent_per_sec": self._safe_execute(self._get_bytes_sent),
            "network_bytes_recv_per_sec": self._safe_execute(self._get_bytes_recv),
            "network_connections": self._safe_execute(self._get_connections),
        }

        self.logger.info("Network metrics collected", **metrics)
        return metrics

    def _get_bytes_sent(self) -> float:
        """Get bytes sent per second (delta over 1 second)."""
        try:
            io1 = psutil.net_io_counters()
            time.sleep(1)
            io2 = psutil.net_io_counters()
            return (io2.bytes_sent - io1.bytes_sent) / 1024 / 1024  # MB/s
        except Exception as e:
            self.logger.warning(f"Failed to get bytes sent: {e}")
            return 0.0

    def _get_bytes_recv(self) -> float:
        """Get bytes received per second (delta over 1 second)."""
        try:
            io1 = psutil.net_io_counters()
            time.sleep(1)
            io2 = psutil.net_io_counters()
            return (io2.bytes_recv - io1.bytes_recv) / 1024 / 1024  # MB/s
        except Exception as e:
            self.logger.warning(f"Failed to get bytes received: {e}")
            return 0.0

    def _get_connections(self) -> int:
        """Get count of active TCP connections."""
        try:
            return len(psutil.net_connections(kind="tcp"))
        except Exception as e:
            self.logger.warning(f"Failed to get connections: {e}")
            return 0

    def is_healthy(self, metrics: Optional[Dict[str, Any]] = None) -> bool:
        """Check if network metrics are within thresholds.

        Args:
            metrics: Already-collected metrics dict from this same cycle.
                Pass this to skip a second collect() - each collect() here
                costs roughly 2s just from the two I/O-delta sleeps, so a
                redundant call is real wall-clock cost, not just noise.
        """
        if metrics is None:
            metrics = self.collect()
        connections_ok = metrics["network_connections"] < self.get_threshold("network.max_connections", 500)
        # Latency threshold can be added later
        return connections_ok
