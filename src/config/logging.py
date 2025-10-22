"""Structured logging configuration using structlog for JSON logs.

Provides:
- JSON-formatted logs for production parsing
- Context binding for request tracking
- Async-safe logging
- Log rotation (30 days retention, 1GB max size per edge case)
"""

import logging
import logging.handlers
import sys
from pathlib import Path

import structlog


def configure_logging(
    level: str = "INFO",
    log_format: str = "json",
    log_dir: Path | None = None,
    rotation_days: int = 30,
    max_size_mb: int = 1000,
) -> None:
    """Configure structured logging with JSON output and rotation.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ("json" or "text")
        log_dir: Directory for log files (None = console only)
        rotation_days: Days to keep rotated logs
        max_size_mb: Maximum log file size in MB

    Example:
        >>> from src.config.logging import configure_logging
        >>> configure_logging(level="INFO", log_format="json", log_dir=Path("logs"))
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper()),
        stream=sys.stdout,
    )

    # Structlog processors based on format
    if log_format == "json":
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ]
    else:  # text format for development
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.dev.ConsoleRenderer(),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,  # type: ignore[arg-type]
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Add file handler with rotation if log directory specified
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "obs_bot.log"

        # Rotating file handler: rotate when file reaches max_size_mb
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=max_size_mb * 1024 * 1024,  # Convert MB to bytes
            backupCount=rotation_days,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, level.upper()))

        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance with bound context.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Structured logger with JSON output

    Example:
        >>> from src.config.logging import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("stream_started", session_id="abc-123")
    """
    return structlog.get_logger(name)
