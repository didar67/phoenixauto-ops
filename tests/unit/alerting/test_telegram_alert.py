"""Unit tests for TelegramAlertSender's Bot API integration."""
import pytest
import requests

from app.alerting.telegram import TelegramAlertSender


@pytest.fixture
def sender(patch_config):
    patch_config(get_values={"telegram.bot_token": "test-token", "telegram.chat_id": "-100123"})
    return TelegramAlertSender()


class TestSend:
    def test_posts_to_telegram_sendmessage_endpoint(self, sender, mocker):
        mock_post = mocker.patch("app.alerting.telegram.requests.post")
        mock_post.return_value.raise_for_status.return_value = None

        sender._send("CRITICAL Alert: cpu_usage_percent exceeded threshold")

        called_url = mock_post.call_args[0][0]
        called_payload = mock_post.call_args.kwargs["json"]
        assert called_url == "https://api.telegram.org/bottest-token/sendMessage"
        assert called_payload["chat_id"] == "-100123"
        assert called_payload["text"] == "CRITICAL Alert: cpu_usage_percent exceeded threshold"

    def test_raises_on_http_error_so_caller_can_track_failure(self, sender, mocker):
        mock_post = mocker.patch("app.alerting.telegram.requests.post")
        mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "401 Unauthorized"
        )

        with pytest.raises(requests.exceptions.HTTPError):
            sender._send("test message")

    def test_missing_credentials_skips_send_without_error(self, patch_config, mocker):
        patch_config(get_values={})  # no bot_token / chat_id configured
        sender = TelegramAlertSender()
        mock_post = mocker.patch("app.alerting.telegram.requests.post")

        sender._send("test message")

        mock_post.assert_not_called()
        