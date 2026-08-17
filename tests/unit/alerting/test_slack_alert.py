"""Unit tests for SlackAlertSender's Incoming Webhook integration."""
import pytest
import requests

from app.alerting.slack import SlackAlertSender


@pytest.fixture
def sender(patch_config):
    patch_config(get_values={"slack.webhook_url": "https://hooks.slack.com/services/T0/B0/xyz"})
    return SlackAlertSender()


class TestSend:
    def test_posts_message_payload_to_webhook_url(self, sender, mocker):
        mock_post = mocker.patch("app.alerting.slack.requests.post")
        mock_post.return_value.raise_for_status.return_value = None

        sender._send("WARNING Alert: disk_usage_percent exceeded threshold")

        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "https://hooks.slack.com/services/T0/B0/xyz"
        assert mock_post.call_args.kwargs["json"] == {
            "text": "WARNING Alert: disk_usage_percent exceeded threshold"
        }

    def test_webhook_rejection_propagates_as_http_error(self, sender, mocker):
        mock_post = mocker.patch("app.alerting.slack.requests.post")
        mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 channel not found"
        )

        with pytest.raises(requests.exceptions.HTTPError):
            sender._send("test message")

    def test_missing_webhook_url_skips_send(self, patch_config, mocker):
        patch_config(get_values={})
        sender = SlackAlertSender()
        mock_post = mocker.patch("app.alerting.slack.requests.post")

        sender._send("test message")

        mock_post.assert_not_called()
        