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

        # Set by shutdown() when main.py catches SIGTERM/SIGINT. run_forever()
        # checks this between cycles (and during the inter-cycle sleep) so a
        # `docker stop` / `docker compose down` finishes the in-flight cycle
        # instead of getting killed mid-healing-action.
        self._shutdown_requested = False

        logger.info("Monitoring engine initialized")

    def run_cycle(self) -> None:
        """Execute one full monitoring/alerting/healing cycle."""
        logger.info("Starting monitoring cycle")

        try:
            # 1. Collect metrics
            system_data = self.system_metrics.collect()
            network_data = self.network_metrics.collect()

            # 2. Check thresholds and alert
            if not self.system_metrics.is_healthy(system_data):
                self._send_alert("system_health", system_data)

            if not self.network_metrics.is_healthy(network_data):
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

    def shutdown(self) -> None:
        """Request a graceful stop after the current cycle finishes.

        Called from main.py's SIGTERM handler. Does not interrupt a cycle
        already in progress - it just stops the next one from starting.
        """
        logger.info("Shutdown requested - will stop after current cycle")
        self._shutdown_requested = True

    def _interruptible_sleep(self, seconds: int) -> None:
        """Sleep in 1s increments so shutdown() takes effect within ~1s
        instead of waiting out the full cycle_interval - matters when
        cycle_interval is large (e.g. 60s) and SIGTERM arrives mid-sleep.
        """
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