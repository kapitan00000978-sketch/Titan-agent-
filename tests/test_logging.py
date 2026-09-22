"""
Phase 15 — Structured JSON logging + GET /api/logs/recent.

Deterministic, network-free:
- JsonFormatter renders a LogRecord as one JSON object (extra fields preserved).
- RingBufferHandler mirrors records into the bounded in-memory LOG_RING.
- setup_logging() is idempotent (exactly one stream + one ring handler).
- The live `/api/logs/recent` endpoint (auth-protected) serves the ring.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

from titan_agent.logging_setup import (
    LOG_RING,
    JsonFormatter,
    RingBufferHandler,
    setup_logging,
)

# Echo the same env-key pattern used by the other server test modules.
_TEST_KEY = "sk-logs-" + uuid.uuid4().hex
os.environ["TITAN_API_KEY"] = _TEST_KEY

from titan_agent.server import app  # (import for the live endpoint)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ.get('TITAN_API_KEY', _TEST_KEY)}"}


def _fresh_logger(tag: str) -> logging.Logger:
    """An isolated child logger of the titan_agent tree (records propagate to
    the parent JSON handlers -> ring)."""
    return logging.getLogger(f"titan_agent.test.{tag}")


def _emit(logger: logging.Logger, level: int, msg: str, **extra: object) -> None:
    logger.log(level, msg, extra=extra)


# ---------------------------------------------------------------------------
# Formatter: single JSON line, extras preserved, traceback rendered.
# ---------------------------------------------------------------------------

def test_json_formatter_emits_structured_record() -> None:
    record = logging.LogRecord(
        name="titan_agent.test.formatter",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="pipeline started",
        args=(),
        exc_info=None,
    )
    record.event = "generation_start"  # custom extra
    record.run_id = "run-123"
    line = JsonFormatter().format(record)
    payload = json.loads(line)  # must be valid JSON
    assert payload["level"] == "INFO"
    assert payload["logger"] == "titan_agent.test.formatter"
    assert payload["message"] == "pipeline started"
    assert payload["event"] == "generation_start"
    assert payload["run_id"] == "run-123"
    assert "ts" in payload


def test_json_formatter_renders_traceback_on_exception() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()
        line = JsonFormatter().format(logging.LogRecord(
            name="x", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="failed", args=(), exc_info=exc_info,
        ))
    payload = json.loads(line)
    assert "ValueError: boom" in payload["traceback"]
    assert payload["level"] == "ERROR"


def test_json_formatter_never_leaks_standard_attributes() -> None:
    record = logging.LogRecord(
        name="n", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="w", args=(), exc_info=None,
    )
    payload = json.loads(JsonFormatter().format(record))
    # `asctime`/`created`/`process` etc. are standard record attrs — extras that
    # escaped the filter (like `pathname`-ish keys via __dict__) must not appear.
    for key in ("created", "process", "thread", "lineno", "filename"):
        assert key not in payload, f"standard attr leaked: {key}"


# ---------------------------------------------------------------------------
# Ring buffer: bounded, in-memory, ordered.
# ---------------------------------------------------------------------------

def test_ring_handler_mirrors_records_into_log_ring() -> None:
    setup_logging()
    before = len(LOG_RING)
    marker = f"ring-marker-{uuid.uuid4().hex[:8]}"
    _emit(_fresh_logger("ring"), logging.INFO, marker, event="ring_test")
    after = len(LOG_RING)
    assert after > before, "the ring must grow when a record is emitted"
    assert LOG_RING[-1]["message"] == marker
    assert LOG_RING[-1]["event"] == "ring_test"
    assert LOG_RING[-1]["level"] == "INFO"


def test_ring_handler_ignores_unserializable_extras() -> None:
    setup_logging()
    marker = f"odd-extras-{uuid.uuid4().hex[:8]}"
    logger = _fresh_logger("ring-odd")

    class Weird:
        def __repr__(self):  # pragma: no cover - never reached
            return "<weird>"

    # `default=str` in json.dumps means even exotic objects survive; the handler
    # must never raise and must still append a usable record.
    _emit(logger, logging.INFO, marker, blobby=Weird())
    assert LOG_RING[-1]["message"] == marker


def test_setup_logging_is_idempotent() -> None:
    logger = setup_logging()
    configs = getattr(logger, "_titan_json_configured", False)
    assert configs is True
    handlers = [h for h in logger.handlers]
    # A second call adds nothing.
    setup_logging()
    assert logger.handlers == handlers
    assert len([h for h in handlers if isinstance(h, RingBufferHandler)]) == 1


def test_titan_agent_logger_disables_propagation_to_root() -> None:
    logger = setup_logging()
    assert logger.propagate is False


# ---------------------------------------------------------------------------
# Live endpoint: auth + filtering + ordering.
# ---------------------------------------------------------------------------

def test_logs_recent_requires_auth(client: TestClient) -> None:
    assert client.get("/api/logs/recent").status_code == 401
    assert client.get("/api/logs/recent", headers=auth()).status_code == 200


def test_logs_recent_returns_newest_first(client: TestClient) -> None:
    setup_logging()
    marker_a = f"log-a-{uuid.uuid4().hex[:8]}"
    marker_b = f"log-b-{uuid.uuid4().hex[:8]}"
    _emit(_fresh_logger("endpoint"), logging.INFO, marker_a)
    _emit(_fresh_logger("endpoint"), logging.INFO, marker_b)

    body = client.get("/api/logs/recent?limit=20", headers=auth()).json()
    assert body["level_filter"] is None
    messages = [r["message"] for r in body["logs"]]
    # Newest first → marker_b precedes marker_a.
    assert messages.index(marker_b) < messages.index(marker_a)


def test_logs_recent_level_filter(client: TestClient) -> None:
    setup_logging()
    marker_info = f"info-{uuid.uuid4().hex[:8]}"
    marker_warn = f"warn-{uuid.uuid4().hex[:8]}"
    _emit(_fresh_logger("level"), logging.INFO, marker_info)
    _emit(_fresh_logger("level"), logging.WARNING, marker_warn)

    warns = client.get("/api/logs/recent?level=WARNING&limit=50", headers=auth()).json()
    assert warns["level_filter"] == "WARNING"
    warn_msgs = [r["message"] for r in warns["logs"]]
    assert marker_warn in warn_msgs
    assert marker_info not in warn_msgs


def test_logs_recent_limit_is_clamped(client: TestClient) -> None:
    setup_logging()
    body = client.get("/api/logs/recent?limit=5", headers=auth()).json()
    assert len(body["logs"]) <= 5
    assert body["total"] >= 0

    # Pathological limit values still resolve to a sane range.
    bad = client.get("/api/logs/recent?limit=-7", headers=auth()).json()
    assert len(bad["logs"]) == 1  # max(1, ...) floor