"""
PhoenixAuto-Ops Slack Alert Sender

Concrete implementation of BaseAlertSender for Slack Webhook.
Sends formatted alerts to a Slack channel using Incoming Webhook.
"""

import requests

from app.alerting.base import BaseAlertSender
from app.utils.logger import logger


class SlackAlertSender(BaseAlertSender):
    """Slack Incoming Webhook alert sender.

    Inherits cooldown, message formatting and error handling from BaseAlertSender.
    Uses simple POST request to Slack webhook URL.
    """

    def __init__(self) -> None:
        """Load Slack webhook URL from config."""
        super().__init__()
        self.webhook_url = self.config.get("slack.webhook_url")

        if not self.webhook_url:
            self.logger.warning("Slack webhook URL missing in config. Alerts will be skipped.")

    def _send(self, message: str) -> None:
        """Send message to Slack via Incoming Webhook."""
        if not self.webhook_url:
            self.logger.warning("Skipping Slack alert - missing webhook URL")
            return

        payload = {"text": message}

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            self.logger.debug("Slack message sent successfully")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Slack webhook request failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error sending Slack alert: {e}")
            raise