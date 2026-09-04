"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    json_format: bool = False,
) -> None:
    """Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        json_format: If True, output JSON-structured logs
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    if json_format:
        try:
            import structlog
            structlog.configure(
                processors=[
                    structlog.stdlib.filter_by_level,
                    structlog.stdlib.add_logger_name,
                    structlog.stdlib.add_log_level,
                    structlog.stdlib.PositionalArgumentsFormatter(),
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.StackInfoRenderer(),
                    structlog.processors.format_exc_info,
                    structlog.processors.UnicodeDecoder(),
                    structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
                ],
                wrapper_class=structlog.stdlib.BoundLogger,
                context_class=dict,
                logger_factory=structlog.stdlib.LoggerFactory(),
                cache_logger_on_first_use=True,
            )
            formatter = structlog.stdlib.ProcessorFormatter(
                processor=structlog.dev.ConsoleRenderer()
            )
            console_handler.setFormatter(formatter)
        except ImportError:
            # Fallback to standard formatting if structlog not installed
            console_handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            ))
    else:
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        ))

    root_logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        ))
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given module name."""
    return logging.getLogger(name)
