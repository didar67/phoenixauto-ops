"""
PhoenixAuto-Ops Engine
=====================

Core orchestration logic for the entire system.
Coordinates monitoring, alerting, and self-healing cycles.
"""

import time

from app.monitoring.system import SystemMetrics
from app.monitoring.network import NetworkMetrics
from app.alerting.telegram import TelegramAlertSender
from app.alerting.slack import SlackAlertSender
from app.healing.actions import HealingActions
from app.utils.logger import logger
from app.utils.config_loader import config


class MonitoringEngine:
    """Main engine to run monitoring, alerting, and healing cycles."""

    def __init__(self) -> None:
        """Initialize all modules."""
        self.system_metrics = SystemMetrics()
        self.network_metrics = NetworkMetrics()
        self.telegram_alert = TelegramAlertSender()
        self.slack_alert = SlackAlertSender()
        self.healing = HealingActions()
        self.cycle_interval = config.get("engine.cycle_interval_seconds", 60)

        logger.info("Monitoring engine initialized")

    def run_cycle(self) -> None:
        """Execute one full monitoring/alerting/healing cycle."""
        logger.info("Starting monitoring cycle")

        try:
            # 1. Collect metrics
            system_data = self.system_metrics.collect()
            network_data = self.network_metrics.collect()

            # 2. Check thresholds and alert
            if not self.system_metrics.is_healthy():
                self._send_alert("system_health", system_data)

            if not self.network_metrics.is_healthy():
                self._send_alert("network_health", network_data)

            # 3. Trigger healing if needed
            if self.healing.healing_enabled:
                self._trigger_healing(system_data, network_data)

            logger.info("Monitoring cycle completed successfully")
        except Exception as e:
            logger.error("Error in monitoring cycle", extra={"error": str(e)})

    def _send_alert(self, metric_key: str, data: dict) -> None:
        """Send alert via available channels."""
        threshold = config.get_threshold(metric_key, 80.0)
        value = data.get(metric_key, 0.0)

        if value > threshold:
            message = f"CRITICAL: {metric_key} exceeded threshold ({value} > {threshold})"
            logger.warning(message)

            self.telegram_alert.send_alert(metric_key, value, threshold, "critical")
            self.slack_alert.send_alert(metric_key, value, threshold, "critical")

    def _trigger_healing(self, system_data: dict, network_data: dict) -> None:
        """Trigger appropriate healing actions."""
        logger.info("Triggering self-healing actions")

        if system_data.get("cpu_usage_percent", 0) > 90:
            self.healing.restart_service("high-cpu-service")  # example

        if system_data.get("memory_usage_percent", 0) > 95:
            self.healing.clear_cache()

        if network_data.get("network_connections", 0) > 400:
            self.healing.kill_process("high-connection-process")

    def run_forever(self) -> None:
        """Run continuous monitoring loop."""
        while True:
            self.run_cycle()
            time.sleep(self.cycle_interval)