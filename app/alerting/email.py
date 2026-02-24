"""
PhoenixAuto-Ops Email Alert Sender

Concrete implementation of BaseAlertSender for SMTP email delivery.
Supports Gmail, Outlook, or any standard SMTP server with SSL.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.alerting.base import BaseAlertSender
from app.utils.logger import logger


class EmailAlertSender(BaseAlertSender):
    """SMTP-based email alert sender.

    Inherits cooldown, formatting and error handling from BaseAlertSender.
    Uses secure SMTP_SSL for email delivery.
    """

    def __init__(self) -> None:
        """Load email credentials from config."""
        super().__init__()
        self.smtp_server = self.config.get("email.smtp_server")
        self.smtp_port = self.config.get("email.smtp_port", 465)
        self.username = self.config.get("email.username")
        self.password = self.config.get("email.password")
        self.from_email = self.config.get("email.from_email")
        self.to_email = self.config.get("email.to_email")

        if not all([self.smtp_server, self.username, self.password, self.from_email, self.to_email]):
            self.logger.warning("Email credentials missing in config. Email alerts will be skipped.")

    def _send(self, message: str) -> None:
        """Send email using SMTP_SSL."""
        if not all([self.smtp_server, self.username, self.password, self.from_email, self.to_email]):
            self.logger.warning("Skipping email alert - missing credentials")
            return

        try:
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = self.to_email
            msg['Subject'] = "PhoenixAuto-Ops Alert"

            msg.attach(MIMEText(message, 'plain'))

            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.login(self.username, self.password)
                server.send_message(msg)

            self.logger.debug("Email alert sent successfully")
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")
            raise