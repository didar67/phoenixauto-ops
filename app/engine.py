"""
PhoenixAuto-Ops Engine
=====================

Core orchestration logic for the entire system.
Coordinates monitoring, alerting, and self-healing cycles.
"""

import time

from app.alerting.email import EmailAlertSender
from app.alerting.slack import SlackAlertSender
from app.alerting.telegram import TelegramAlertSender
from app.healing.actions import HealingActions
from app.monitoring.network import NetworkMetrics
from app.monitoring.system import SystemMetrics
from app.utils.config_loader import config
from app.utils.logger import logger

# Maps each key that collect() actually returns to the config key holding
# its threshold. Kept explicit rather than assuming they match 1:1 -
# load_average's threshold is named load_average_limit, not load_average.
_SYSTEM_METRIC_THRESHOLDS = {
    "cpu_usage_percent": "cpu_usage_percent",
    "memory_usage_percent": "memory_usage_percent",
    "disk_usage_percent": "disk_usage_percent",
    "load_average": "load_average_limit",
}

_NETWORK_METRIC_THRESHOLDS = {
    "network_connections": "network.max_connections",
}


class MonitoringEngine:
    """Main engine to run monitoring, alerting, and healing cycles."""

    def __init__(self) -> None:
        """Initialize all modules."""
        self.system_metrics = SystemMetrics()
        self.network_metrics = NetworkMetrics()
        self.telegram_alert = TelegramAlertSender()
        self.slack_alert = SlackAlertSender()
        self.email_alert = EmailAlertSender()
        self.healing = HealingActions()
        self.cycle_interval = config.get("engine.cycle_interval_seconds", 60)

        # Set by shutdown() when main.py catches SIGTERM/SIGINT.
        self._shutdown_requested = False

        logger.info("Monitoring engine initialized")

    def run_cycle(self) -> None:
        """Execute one full monitoring/alerting/healing cycle."""
        logger.info("Starting monitoring cycle")

        try:
            system_data = self.system_metrics.collect()
            network_data = self.network_metrics.collect()

            if not self.system_metrics.is_healthy(system_data):
                self._check_and_alert(system_data, _SYSTEM_METRIC_THRESHOLDS)

            if not self.network_metrics.is_healthy(network_data):
                self._check_and_alert(network_data, _NETWORK_METRIC_THRESHOLDS)

            if self.healing.healing_enabled:
                self._trigger_healing(system_data, network_data)

            logger.info("Monitoring cycle completed successfully")
        except Exception as e:
            logger.error("Error in monitoring cycle", extra={"error": str(e)})

    def _check_and_alert(self, data: dict, metric_thresholds: dict) -> None:
        """Compare each metric against its own threshold and alert on breach.

        Replaces the old lookup on a synthetic 'system_health'/'network_health'
        key that never existed in the collected data - that always compared
        a missing value (0.0) against a missing threshold default, so no
        alert ever actually fired regardless of real breaches.
        """
        for metric_key, threshold_key in metric_thresholds.items():
            value = data.get(metric_key)
            if value is None:
                continue

            threshold = config.get_threshold(threshold_key, default=float("inf"))
            if value > threshold:
                self._send_alert(metric_key, value, threshold)

    def _send_alert(self, metric_key: str, value: float, threshold: float) -> None:
        """Dispatch a single breach alert across every configured channel."""
        logger.warning(f"CRITICAL: {metric_key} exceeded threshold ({value} > {threshold})")

        self.telegram_alert.send_alert(metric_key, value, threshold, "critical")
        self.slack_alert.send_alert(metric_key, value, threshold, "critical")
        self.email_alert.send_alert(metric_key, value, threshold, "critical")

    def _trigger_healing(self, system_data: dict, network_data: dict) -> None:
        """Trigger appropriate healing actions.

        Reads the same thresholds.yaml values the alerting path uses, instead
        of separate hardcoded numbers - those had drifted out of sync with
      config (e.g. network healing checked >400 while the configured alert
          threshold was 5), so a breach could alert without ever healing.
        """
        logger.info("Triggering self-healing actions")

        cpu = system_data.get("cpu_usage_percent", 0)
        if cpu > config.get_threshold("cpu_usage_percent"):
            self.healing.restart_service("high-cpu-service")

        memory = system_data.get("memory_usage_percent", 0)
        if memory > config.get_threshold("memory_usage_percent"):
            self.healing.clear_cache()

        connections = network_data.get("network_connections", 0)
        if connections > config.get_threshold("network.max_connections", 500):
            self.healing.kill_process("high-connection-process")

    def shutdown(self) -> None:
        """Request a graceful stop after the current cycle finishes."""
        logger.info("Shutdown requested - will stop after current cycle")
        self._shutdown_requested = True

    def _interruptible_sleep(self, seconds: int) -> None:
        """Sleep in 1s increments so shutdown() takes effect within ~1s."""
        slept = 0
        while slept < seconds and not self._shutdown_requested:
            time.sleep(min(1, seconds - slept))
            slept += 1

    def run_forever(self) -> None:
        """Run continuous monitoring loop until a shutdown is requested."""
        while not self._shutdown_requested:
            self.run_cycle()
            self._interruptible_sleep(self.cycle_interval)

        logger.info("Monitoring engine stopped")
