"""
PhoenixAuto-Ops Telegram Alert Sender

Concrete implementation of BaseAlertSender for Telegram Bot API.
Sends formatted alerts to a specific chat/channel with proper error handling.
"""

import requests

from app.alerting.base import BaseAlertSender
from app.utils.logger import logger


class TelegramAlertSender(BaseAlertSender):
    """Telegram Bot API alert sender.

    Inherits cooldown, formatting and error handling from BaseAlertSender.
    Uses requests to call Telegram sendMessage endpoint.
    """

    def __init__(self) -> None:
        """Load Telegram credentials from config."""
        super().__init__()
        self.bot_token = self.config.get("telegram.bot_token")
        self.chat_id = self.config.get("telegram.chat_id")

        if not self.bot_token or not self.chat_id:
            self.logger.warning("Telegram credentials missing in config. Alerts will be skipped.")

    def _send(self, message: str) -> None:
        """Send message via Telegram Bot API."""
        if not self.bot_token or not self.chat_id:
            self.logger.warning("Skipping Telegram alert - missing credentials")
            return

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            self.logger.debug("Telegram message sent successfully")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Telegram API request failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error sending Telegram alert: {e}")
            raise