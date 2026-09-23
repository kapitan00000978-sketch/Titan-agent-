"""Phase 22: per-tool execution telemetry.

Every tool call funnels through `TitanAgent.execute_tool_unified`, which now
records success/failure, latency and output size on a shared (thread-safe)
collector. The agent can query its own record mid-run (`tool_stats` tool) to
stop re-attempting tools that keep failing, and the server exposes the same
record via `GET /api/tools/stats`.

`prompt_block()` is the adaptive hint: when TITAN_TOOL_RECORD=1, tools with
≥3 calls and at least one failure are surfaced in the system prompt so the
model adapts ("tool X failed 40% of the time — prefer the working pattern").
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .core.tools.reliability import ToolReliabilityTracker

log = logging.getLogger(__name__)


class ToolStatsCollector:
    """Bounded, thread-safe, in-memory record of tool executions."""

    def __init__(self, history: int = 2000) -> None:
        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] = []
        self._history = max(1, int(history))

    def record(
        self,
        name: str,
        *,
        ok: bool,
        latency_ms: float,
        error: str | None = None,
        output_chars: int = 0,
    ) -> None:
        """Append one execution event (never raises, bounded history)."""
        with self._lock:
            self._events.append(
                {
                    "tool": name,
                    "ok": bool(ok),
                    "latency_ms": round(float(latency_ms), 1),
                    "error": error,
                    "output_chars": int(output_chars),
                    "ts": round(time.time(), 3),
                }
            )
            if len(self._events) > self._history:
                del self._events[: len(self._events) - self._history]
        try:
            TOOL_RELIABILITY.record_call(name, ok, latency_ms=latency_ms, error=error)
        except (RuntimeError, TypeError, ValueError, KeyError) as exc:
            log.debug("reliability record failed for %s: %s", name, exc)

    def clear(self) -> None:
        with self._lock:
            self._events = []

    def summary(self) -> dict[str, Any]:
        """Per-tool aggregates + overall totals (pure, no side effects)."""
        with self._lock:
            events = list(self._events)
        per: dict[str, dict[str, Any]] = {}
        for ev in events:
            cur = per.setdefault(
                ev["tool"],
                {
                    "calls": 0,
                    "ok": 0,
                    "errors": 0,
                    "latency_ms": 0.0,
                    "output_chars": 0,
                    "last_error": None,
                },
            )
            cur["calls"] += 1
            cur["latency_ms"] += ev["latency_ms"]
            cur["output_chars"] += ev["output_chars"]
            if ev["ok"]:
                cur["ok"] += 1
            else:
                cur["errors"] += 1
                cur["last_error"] = ev["error"] or "failed"
        tools: dict[str, Any] = {}
        for tool, cur in per.items():
            tools[tool] = {
                "calls": cur["calls"],
                "ok": cur["ok"],
                "errors": cur["errors"],
                "error_rate": round(cur["errors"] / cur["calls"], 3),
                "avg_latency_ms": round(cur["latency_ms"] / cur["calls"], 1),
                "avg_output_chars": round(cur["output_chars"] / cur["calls"], 1),
                "last_error": cur["last_error"],
            }
        return {
            "totals": {
                "calls": len(events),
                "ok": sum(1 for e in events if e["ok"]),
                "errors": sum(1 for e in events if not e["ok"]),
            },
            "tools": tools,
        }

    def prompt_block(self, max_tools: int = 8, min_calls: int = 3) -> str:
        """Adaptive hint for the system prompt: only tools with repeat failures.

        Empty string when nothing is worth surfacing, so the common prompt is
        byte-for-byte unchanged.
        """
        per = self.summary().get("tools", {})
        ranked = sorted(
            (
                (name, d)
                for name, d in per.items()
                if d["calls"] >= min_calls and d["errors"] > 0
            ),
            key=lambda nd: -nd[1]["error_rate"],
        )
        if not ranked:
            return ""
        lines = []
        for name, d in ranked[: max(1, max_tools)]:
            rate = d["errors"] / d["calls"] if d["calls"] else 0.0
            lines.append(
                f"- {name}: {d['calls']} calls, {d['errors']} failed "
                f"({rate:.0%}), avg {d['avg_latency_ms']:.0f}ms, "
                f"last error: {d['last_error']}"
            )
        return (
            "### TOOL RECORD (recent tool failures this process — adapt):\n"
            + "\n".join(lines)
            + "\n\nPrefer tools with a healthy record; if a tool keeps failing, "
            "switch approach instead of repeating it."
        )


# Shared process-wide collector: the agent default AND the server endpoint read
# the same instance, so failures persist across runs on one process.
TOOL_STATS = ToolStatsCollector()
TOOL_RELIABILITY = ToolReliabilityTracker()