"""Unit tests for BaseAlertSender's cooldown/formatting contract,
exercised through TelegramAlertSender since BaseAlertSender is abstract."""
from datetime import datetime, timedelta

import pytest

from app.alerting.telegram import TelegramAlertSender


@pytest.fixture
def sender(patch_config, mocker):
    patch_config(
        get_values={
            "telegram.bot_token": "test-token",
            "telegram.chat_id": "123456",
            "alerting.cooldown_minutes": 15,
        }
    )
    instance = TelegramAlertSender()
    mocker.patch.object(instance, "_send")
    return instance


class TestSendAlert:
    def test_first_alert_for_a_metric_always_sends(self, sender):
        sent = sender.send_alert("cpu_usage_percent", 95.0, 80.0, "critical")

        assert sent is True
        sender._send.assert_called_once()
        assert "cpu_usage_percent" in sender._send.call_args[0][0]

    def test_repeat_alert_within_cooldown_is_suppressed(self, sender):
        sender.send_alert("cpu_usage_percent", 95.0, 80.0, "critical")
        sender._send.reset_mock()

        sent_again = sender.send_alert("cpu_usage_percent", 96.0, 80.0, "critical")

        assert sent_again is False
        sender._send.assert_not_called()

    def test_alert_resumes_once_cooldown_window_has_elapsed(self, sender):
        sender.send_alert("cpu_usage_percent", 95.0, 80.0, "critical")
        sender._send.reset_mock()
        sender.last_sent["cpu_usage_percent"] = datetime.now() - timedelta(minutes=16)

        sent_again = sender.send_alert("cpu_usage_percent", 96.0, 80.0, "critical")

        assert sent_again is True
        sender._send.assert_called_once()

    def test_different_metrics_have_independent_cooldowns(self, sender):
        sender.send_alert("cpu_usage_percent", 95.0, 80.0, "critical")
        sent = sender.send_alert("memory_usage_percent", 90.0, 85.0, "critical")

        assert sent is True

    def test_send_failure_is_caught_and_reported_as_unsent(self, sender):
        sender._send.side_effect = ConnectionError("network unreachable")

        sent = sender.send_alert("cpu_usage_percent", 95.0, 80.0, "critical")

        assert sent is False
        