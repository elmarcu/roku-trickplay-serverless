import json
import logging
from typing import Any, Dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class StructuredLogger:
    """Structured logging for CloudWatch JSON parsing."""

    @staticmethod
    def info(message: str, **kwargs) -> None:
        """Log info level with structured data."""
        log_data = {"level": "INFO", "message": message, **kwargs}
        logger.info(json.dumps(log_data))

    @staticmethod
    def error(message: str, exception: Exception = None, **kwargs) -> None:
        """Log error level with exception details."""
        log_data = {
            "level": "ERROR",
            "message": message,
            **kwargs,
        }
        if exception:
            log_data["exception"] = str(exception)
            log_data["exception_type"] = type(exception).__name__

        logger.error(json.dumps(log_data))

    @staticmethod
    def warning(message: str, **kwargs) -> None:
        """Log warning level with structured data."""
        log_data = {"level": "WARNING", "message": message, **kwargs}
        logger.warning(json.dumps(log_data))

    @staticmethod
    def debug(message: str, **kwargs) -> None:
        """Log debug level with structured data."""
        log_data = {"level": "DEBUG", "message": message, **kwargs}
        logger.debug(json.dumps(log_data))
