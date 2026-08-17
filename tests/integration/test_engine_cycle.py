"""Integration-style tests for MonitoringEngine.run_cycle().

Every collaborator (metrics collectors, alert senders, healing actions) is
mocked, so assertions stay focused on the engine's own orchestration -
psutil, HTTP, and subprocess behavior are already covered by their own
unit test modules.
"""
import pytest

from app.engine import MonitoringEngine


@pytest.fixture
def engine(patch_config, mocker):
    patch_config(
        get_values={"engine.cycle_interval_seconds": 60},
        threshold_values={"system_health": 80.0, "network_health": 500.0},
    )

    mock_system_cls = mocker.patch("app.engine.SystemMetrics")
    mock_network_cls = mocker.patch("app.engine.NetworkMetrics")
    mock_telegram_cls = mocker.patch("app.engine.TelegramAlertSender")
    mock_slack_cls = mocker.patch("app.engine.SlackAlertSender")
    mock_healing_cls = mocker.patch("app.engine.HealingActions")

    instance = MonitoringEngine()
    instance.system_metrics = mock_system_cls.return_value
    instance.network_metrics = mock_network_cls.return_value
    instance.telegram_alert = mock_telegram_cls.return_value
    instance.slack_alert = mock_slack_cls.return_value
    instance.healing = mock_healing_cls.return_value
    instance.healing.healing_enabled = True

    return instance


class TestRunCycle:
    def test_healthy_system_sends_no_alerts(self, engine):
        engine.system_metrics.collect.return_value = {"cpu_usage_percent": 20.0}
        engine.network_metrics.collect.return_value = {"network_connections": 50}
        engine.system_metrics.is_healthy.return_value = True
        engine.network_metrics.is_healthy.return_value = True

        engine.run_cycle()

        engine.telegram_alert.send_alert.assert_not_called()
        engine.slack_alert.send_alert.assert_not_called()

    def test_system_breach_dispatches_alert_on_both_channels(self, engine):
        engine.system_metrics.collect.return_value = {"system_health": 92.0}
        engine.network_metrics.collect.return_value = {"network_connections": 10}
        engine.system_metrics.is_healthy.return_value = False
        engine.network_metrics.is_healthy.return_value = True

        engine.run_cycle()

        engine.telegram_alert.send_alert.assert_called_once_with(
            "system_health", 92.0, 80.0, "critical"
        )
        engine.slack_alert.send_alert.assert_called_once_with(
            "system_health", 92.0, 80.0, "critical"
        )

    def test_a_collector_exception_does_not_crash_the_cycle(self, engine):
        # engine.py wraps run_cycle() in try/except - one bad cycle should
        # be logged and skipped, not take run_forever() down (the
        # container's HEALTHCHECK depends on the loop staying alive).
        engine.system_metrics.collect.side_effect = RuntimeError("psutil backend unavailable")

        engine.run_cycle()  # must not raise

    def test_healing_skipped_when_disabled_in_config(self, engine):
        engine.healing.healing_enabled = False
        engine.system_metrics.collect.return_value = {"cpu_usage_percent": 99.0}
        engine.network_metrics.collect.return_value = {"network_connections": 10}
        engine.system_metrics.is_healthy.return_value = False
        engine.network_metrics.is_healthy.return_value = True

        engine.run_cycle()

        engine.healing.restart_service.assert_not_called()


class TestTriggerHealing:
    def test_high_cpu_triggers_service_restart(self, engine):
        engine._trigger_healing({"cpu_usage_percent": 95.0}, {"network_connections": 10})

        engine.healing.restart_service.assert_called_once_with("high-cpu-service")

    def test_high_memory_triggers_cache_clear(self, engine):
        engine._trigger_healing({"memory_usage_percent": 97.0}, {"network_connections": 10})

        engine.healing.clear_cache.assert_called_once()

    def test_high_connection_count_triggers_process_kill(self, engine):
        engine._trigger_healing({"cpu_usage_percent": 10.0}, {"network_connections": 450})

        engine.healing.kill_process.assert_called_once_with("high-connection-process")

    def test_nothing_triggered_when_all_metrics_nominal(self, engine):
        engine._trigger_healing(
            {"cpu_usage_percent": 30.0, "memory_usage_percent": 40.0},
            {"network_connections": 50},
        )

        engine.healing.restart_service.assert_not_called()
        engine.healing.clear_cache.assert_not_called()
        engine.healing.kill_process.assert_not_called()


class TestShutdown:
    def test_shutdown_sets_flag_checked_by_run_forever(self, engine):
        assert engine._shutdown_requested is False

        engine.shutdown()

        assert engine._shutdown_requested is True

    def test_interruptible_sleep_exits_early_once_shutdown_requested(self, engine, mocker):
        mock_sleep = mocker.patch("app.engine.time.sleep")
        call_count = 0

        def _sleep_side_effect(_seconds):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                engine._shutdown_requested = True

        mock_sleep.side_effect = _sleep_side_effect

        engine._interruptible_sleep(60)

        assert mock_sleep.call_count == 2
        