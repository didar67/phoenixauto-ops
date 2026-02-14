"""
PhoenixAuto-Ops Structured Logger
=================================

Centralized, production-ready logging utility for the entire project.
Features:
- Console output (human readable for development)
- Rotating file logs (daily rotation, 7 days retention)
- JSON structured format for file logs (easy to parse by tools)
- Singleton pattern to prevent duplicate handlers
- Automatic integration with ConfigLoader for log level
- Supports extra contextual data (structured logging)
- Robust error handling with fallbacks

Usage:
    from app.utils.logger import logger
    logger.info("Monitoring cycle started", cpu=45.2, memory=67.8)
    logger.error("Service restart failed", exc_info=True)
"""

import json
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from app.utils.config_loader import config


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging in files."""

    def format(self, record: logging.LogRecord) -> str:
        """Convert log record to JSON with extra context, safely."""
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Safely add extra contextual data
        extra_data = getattr(record, "extra", None)
        if extra_data is not None:
            try:
                log_entry.update(extra_data)
            except Exception:
                log_entry["extra_error"] = "Failed to serialize extra data"

        # Safely add exception info
        if record.exc_info:
            try:
                log_entry["exception"] = self.formatException(record.exc_info)
            except Exception:
                log_entry["exception"] = "Failed to format exception"

        try:
            return json.dumps(log_entry, ensure_ascii=False, default=str)
        except Exception as e:
            # Fallback to plain text if JSON fails
            return f'{{"error": "JSON serialization failed: {str(e)}", "original_message": "{log_entry["message"]}"}}'


class StructuredLogger:
    """Singleton structured logger for PhoenixAuto-Ops.

    Ensures only one logger instance exists.
    Loads log level from config with fallback.
    Handles setup errors gracefully.
    """

    _instance = None

    def __new__(cls) -> "StructuredLogger":
        """Create or return existing singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_logger()
        return cls._instance

    def _setup_logger(self) -> None:
        """Configure console and rotating file handlers with error handling."""
        self.logger = logging.getLogger("phoenixauto_ops")

        # Load log level from config with fallback
        try:
            log_level_str = config.get("logging.level", "INFO").upper()
            self.logger.setLevel(getattr(logging, log_level_str, logging.INFO))
        except Exception as e:
            self.logger.setLevel(logging.INFO)
            print(f"Warning: Failed to load log level from config: {e}. Using INFO.")

        self.logger.propagate = False  # Prevent duplicate propagation

        # Create logs directory safely
        log_dir = Path("logs")
        try:
            log_dir.mkdir(exist_ok=True)
        except OSError as e:
            print(f"Warning: Could not create logs directory: {e}. Console only.")

        # Console Handler (always added, human readable)
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # File Handler (JSON + rotation) with try-except
        try:
            file_handler = TimedRotatingFileHandler(
                filename=log_dir / "phoenixauto-ops.log",
                when="midnight",
                interval=1,
                backupCount=7,
                encoding="utf-8",
            )
            file_handler.setFormatter(JSONFormatter())
            self.logger.addHandler(file_handler)
            self.logger.info("File logging enabled with rotation")
        except Exception as e:
            self.logger.warning(f"Failed to setup file logging: {e}. Using console only.")

        self.logger.info("Structured logger initialized successfully")

    def debug(self, message: str, **extra: Any) -> None:
        """Log debug level message with optional structured data."""
        self.logger.debug(message, extra=extra)

    def info(self, message: str, **extra: Any) -> None:
        """Log info level message with optional structured data."""
        self.logger.info(message, extra=extra)

    def warning(self, message: str, **extra: Any) -> None:
        """Log warning level message with optional structured data."""
        self.logger.warning(message, extra=extra)

    def error(self, message: str, **extra: Any) -> None:
        """Log error level message with optional structured data."""
        self.logger.error(message, extra=extra)

    def critical(self, message: str, **extra: Any) -> None:
        """Log critical level message with optional structured data."""
        self.logger.critical(message, extra=extra)


# Singleton instance - import and use directly
logger = StructuredLogger()