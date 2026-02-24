"""
Alerting package for PhoenixAuto-Ops.
Exposes key classes for easy import.
"""

from .base import BaseAlertSender
from .telegram import TelegramAlertSender

__all__ = [
    "BaseAlertSender",
    "TelegramAlertSender",
]