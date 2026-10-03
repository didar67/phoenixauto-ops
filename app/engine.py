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

        # Tracks how many *consecutive* cycles each metric has been in
        # breach. A single spiky cycle (a batch job, a brief GC pause)
        # shouldn't trigger an alert or a service restart on its own -
        # only a sustained breach should. Reset to 0 the moment a metric
        # comes back under threshold.
        self._breach_streak: dict = {}

        self._shutdown_requested = False

        logger.info("Monitoring engine initialized")

    def run_cycle(self) -> None:
        """Execute one full monitoring/alerting/healing cycle."""
        logger.info("Starting monitoring cycle")

        try:
            system_data = self.system_metrics.collect()
            network_data = self.network_metrics.collect()

            sustained = {}
            sustained.update(self._update_breach_streaks(system_data, _SYSTEM_METRIC_THRESHOLDS))
            sustained.update(self._update_breach_streaks(network_data, _NETWORK_METRIC_THRESHOLDS))

            for metric_key, (value, threshold) in sustained.items():
                self._send_alert(metric_key, value, threshold)

            if self.healing.healing_enabled:
                self._trigger_healing(system_data, network_data, sustained)

            logger.info("Monitoring cycle completed successfully")
        except Exception as e:
            logger.error("Error in monitoring cycle", extra={"error": str(e)})

    def _update_breach_streaks(self, data: dict, metric_thresholds: dict) -> dict:
        """Update each metric's consecutive-breach counter and return the
        ones that have just crossed the required streak length this cycle.

        Returns: {metric_key: (value, threshold)} for metrics ready to act on.
        """
        required = config.get("auto_healing.consecutive_breaches_required", 3)
        ready_to_act = {}

        for metric_key, threshold_key in metric_thresholds.items():
            value = data.get(metric_key)
            if value is None:
                continue

            threshold = config.get_threshold(threshold_key, default=float("inf"))

            if value > threshold:
                self._breach_streak[metric_key] = self._breach_streak.get(metric_key, 0) + 1
            else:
                self._breach_streak[metric_key] = 0
                continue

            streak = self._breach_streak[metric_key]
            if streak >= required:
                logger.warning(
                    f"CRITICAL: {metric_key} sustained breach for {streak} consecutive cycles "
                    f"({value} > {threshold})"
                )
                ready_to_act[metric_key] = (value, threshold)
            elif streak == 1:
                logger.info(f"{metric_key} breached threshold ({value} > {threshold}) - streak 1/{required}")
            else:
                logger.info(f"{metric_key} still breaching - streak {streak}/{required}")

        return ready_to_act

    def _send_alert(self, metric_key: str, value: float, threshold: float) -> None:
        """Dispatch a single breach alert across every configured channel."""
        self.telegram_alert.send_alert(metric_key, value, threshold, "critical")
        self.slack_alert.send_alert(metric_key, value, threshold, "critical")
        self.email_alert.send_alert(metric_key, value, threshold, "critical")

    def _trigger_healing(self, system_data: dict, network_data: dict, sustained: dict) -> None:
        """Trigger healing only for metrics that just reached a sustained
        breach this cycle. Each action is isolated in its own try/except -
        one action's failure (e.g. restart_service failing in an
        environment with no systemd) must not prevent the other sustained
        breaches in the same cycle from getting their own healing attempt.
        """
        if not sustained:
            return

        logger.info("Triggering self-healing actions")

        if "cpu_usage_percent" in sustained:
            try:
                culprit = self.system_metrics.get_top_cpu_process()
                target = culprit or "high-cpu-service"
                logger.warning(f"High CPU culprit identified: {target}")
                self.healing.restart_service(target)
            except Exception as e:
                logger.error(f"CPU healing action failed: {e}")

        if "memory_usage_percent" in sustained:
            try:
                self.healing.clear_cache()
            except Exception as e:
                logger.error(f"Memory healing action failed: {e}")

        if "network_connections" in sustained:
            try:
                self.healing.kill_process("high-connection-process")
            except Exception as e:
                logger.error(f"Network healing action failed: {e}")

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
