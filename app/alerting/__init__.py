"""
Alerting package for PhoenixAuto-Ops.
Exposes key classes for easy import.
"""

from .base import BaseAlertSender
from .telegram import TelegramAlertSender
from .slack import SlackAlertSender
from .email import EmailAlertSender

__all__ = [
    "BaseAlertSender",
    "TelegramAlertSender",
    "SlackAlertSender",
    "EmailAlertSender",
]