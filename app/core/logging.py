"""Structured logging with automatic redaction of secrets."""

from __future__ import annotations

import logging
import re

_REDACT_PATTERNS: list[re.Pattern] = [
    re.compile(r"(api[_-]?key|password|secret|token|credential)[=: ]+\S+", re.IGNORECASE),
    re.compile(r"Bearer \S+", re.IGNORECASE),
]


class _RedactingFormatter(logging.Formatter):
    """Replaces sensitive tokens in log output with ``***``."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        for pattern in _REDACT_PATTERNS:
            message = pattern.sub(lambda m: m.group(0).split("=")[0] + "=***" if "=" in m.group(0) else "***", message)
        return message


_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

_configured: bool = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger once. Idempotent."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(_RedactingFormatter(_LOG_FORMAT))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Calls *setup_logging* on first use."""
    setup_logging()
    return logging.getLogger(name)
