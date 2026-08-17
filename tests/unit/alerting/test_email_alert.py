"""Unit tests for EmailAlertSender's SMTP_SSL integration."""
import pytest

from app.alerting.email import EmailAlertSender


@pytest.fixture
def sender(patch_config):
    patch_config(
        get_values={
            "email.smtp_server": "smtp.gmail.com",
            "email.smtp_port": 465,
            "email.username": "alerts@example.com",
            "email.password": "app-password",
            "email.from_email": "alerts@example.com",
            "email.to_email": "oncall@example.com",
        }
    )
    return EmailAlertSender()


class TestSend:
    def test_sends_message_through_authenticated_smtp_ssl_session(self, sender, mocker):
        mock_smtp_cls = mocker.patch("app.alerting.email.smtplib.SMTP_SSL")
        mock_smtp = mock_smtp_cls.return_value.__enter__.return_value

        sender._send("CRITICAL Alert: memory_usage_percent exceeded threshold")

        mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 465, timeout=10)
        mock_smtp.login.assert_called_once_with("alerts@example.com", "app-password")
        mock_smtp.send_message.assert_called_once()

    def test_smtp_login_failure_is_reraised(self, sender, mocker):
        mock_smtp_cls = mocker.patch("app.alerting.email.smtplib.SMTP_SSL")
        mock_smtp = mock_smtp_cls.return_value.__enter__.return_value
        mock_smtp.login.side_effect = Exception("535 authentication failed")

        with pytest.raises(Exception, match="authentication failed"):
            sender._send("test message")

    def test_missing_credentials_skips_send(self, patch_config, mocker):
        patch_config(get_values={})
        sender = EmailAlertSender()
        mock_smtp_cls = mocker.patch("app.alerting.email.smtplib.SMTP_SSL")

        sender._send("test message")

        mock_smtp_cls.assert_not_called()
        