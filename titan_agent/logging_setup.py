"""
Structured JSON logging (Phase 15).

Every log line from the ``titan_agent`` logger tree is rendered as a single JSON
object (machine-parseable) AND mirrored into an in-memory ring buffer so the web
UI / API can show "recent logs" without touching the filesystem.

Design:
- ``JsonFormatter``: ts/level/logger/message + any ``extra`` fields + traceback.
- ``RingBufferHandler``: appends the same JSON dict to ``LOG_RING`` (a bounded
  deque, newest at the right end).
- ``setup_logging()``: idempotent — attaches exactly one stream handler and one
  ring handler to the ``titan_agent`` logger and disables propagation so records
  are not ALSO rendered by the root/uvicorn handler (single JSON source of truth).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from collections import deque
from datetime import datetime, timezone
from typing import Any

# Fields that are standard LogRecord attributes — never surfaced as `extra`.
_STANDARD_ATTRS = frozenset(logging.makeLogRecord({}).__dict__)


def _buffer_capacity() -> int:
    try:
        return max(50, int(os.getenv("TITAN_LOG_BUFFER", "500")))
    except (TypeError, ValueError):
        return 500


# Module-level ring; mirrored by RingBufferHandler. Exposed to the server for
# GET /api/logs/recent (each entry is an already-parsed dict).
LOG_RING: deque[dict[str, Any]] = deque(maxlen=_buffer_capacity())


class JsonFormatter(logging.Formatter):
    """Render a LogRecord as one JSON line with extra fields preserved."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["traceback"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class RingBufferHandler(logging.Handler):
    """Keep the last N formatted records in memory (for /api/logs/recent)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            LOG_RING.append(json.loads(self.format(record)))
        except Exception:  # noqa: BLE001 - a logging handler must never raise
            # Standard logging fallback: print to stderr, never raise inside emit.
            self.handleError(record)


def setup_logging(
    level: str | None = None,
    logger_name: str = "titan_agent",
) -> logging.Logger:
    """Configure the titan_agent logger tree for JSON output. Idempotent."""
    logger = logging.getLogger(logger_name)
    lvl_name = (level or os.getenv("TITAN_LOG_LEVEL", "INFO")).strip().upper()
    logger.setLevel(getattr(logging, lvl_name, logging.INFO))

    if getattr(logger, "_titan_json_configured", False):
        return logger

    formatter = JsonFormatter()
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    ring_handler = RingBufferHandler()
    ring_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(ring_handler)
    # Disable upward propagation: the JSON handlers above are the single render
    # path (avoids plain-text duplicates from root/uvicorn/stderr fallback).
    logger.propagate = False
    logger._titan_json_configured = True  # type: ignore[attr-defined]
    return logger