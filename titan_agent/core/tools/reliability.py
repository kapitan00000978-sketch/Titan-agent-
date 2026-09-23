"""
Phase 26 — Genesis Darajasi 8: Tool Reliability Tracker.

Tracks per-tool execution history with Exponentially Weighted Moving Average (EWMA)
reliability scores, health grades (A, B, C, F), and autonomous mitigation recommendations.
"""
from __future__ import annotations

import threading
import time
from typing import Any


class ToolReliabilityTracker:
    """Thread-safe reliability tracker computing EWMA health scores and grades for tools."""

    DEFAULT_ALPHA = 0.3  # EWMA decay factor (recent events weight 30%)

    def __init__(self, alpha: float = DEFAULT_ALPHA):
        self.alpha = max(0.01, min(0.99, alpha))
        self._lock = threading.RLock()
        # tool_name -> stats dict
        self._stats: dict[str, dict[str, Any]] = {}

    def record_call(
        self,
        tool_name: str,
        success: bool,
        latency_ms: float = 0.0,
        error: str | None = None,
    ) -> None:
        """Record an execution outcome for a tool."""
        name = str(tool_name).strip()
        with self._lock:
            stats = self._stats.setdefault(
                name,
                {
                    "calls": 0,
                    "successes": 0,
                    "errors": 0,
                    "consecutive_failures": 0,
                    "score": 1.0,  # Prior optimistic score
                    "avg_latency_ms": 0.0,
                    "last_error": None,
                    "last_updated": time.time(),
                },
            )

            stats["calls"] += 1
            stats["last_updated"] = time.time()
            current_outcome = 1.0 if success else 0.0

            # EWMA update: S_t = alpha * Y_t + (1 - alpha) * S_{t-1}
            stats["score"] = round(
                self.alpha * current_outcome + (1.0 - self.alpha) * stats["score"], 3
            )

            if success:
                stats["successes"] += 1
                stats["consecutive_failures"] = 0
            else:
                stats["errors"] += 1
                stats["consecutive_failures"] += 1
                stats["last_error"] = str(error) if error else "Execution error"

                # Additional penalty for multiple consecutive failures
                if stats["consecutive_failures"] >= 2:
                    penalty = min(0.2, stats["consecutive_failures"] * 0.05)
                    stats["score"] = max(0.0, round(stats["score"] - penalty, 3))

            # Latency moving average
            stats["avg_latency_ms"] = round(
                0.2 * latency_ms + 0.8 * stats["avg_latency_ms"], 1
            )

    def get_score(self, tool_name: str) -> float:
        """Returns the reliability score for a tool between 0.0 and 1.0."""
        with self._lock:
            if tool_name not in self._stats:
                return 1.0  # Unobserved tools start at 1.0
            return self._stats[tool_name]["score"]

    def get_grade(self, tool_name: str) -> str:
        """Returns letter grade: 'A' (>=0.90), 'B' (>=0.75), 'C' (>=0.55), 'F' (<0.55)."""
        score = self.get_score(tool_name)
        if score >= 0.90:
            return "A"
        elif score >= 0.75:
            return "B"
        elif score >= 0.55:
            return "C"
        return "F"

    def is_reliable(self, tool_name: str, threshold: float = 0.55) -> bool:
        """Returns True if the tool meets the reliability threshold."""
        return self.get_score(tool_name) >= threshold

    def get_recommendation(self, tool_name: str) -> str | None:
        """Returns actionable advice if a tool is degraded."""
        with self._lock:
            stats = self._stats.get(tool_name)
            if not stats:
                return None
            score = stats["score"]
            failures = stats["consecutive_failures"]

        if failures >= 3 or score < 0.55:
            return (
                f"Tool '{tool_name}' is unreliable (Grade F, {failures} consecutive fails). "
                "Recommend falling back to alternative tools or verifying arguments."
            )
        elif score < 0.75:
            return f"Tool '{tool_name}' exhibits intermittent errors (Grade C). Proceed with caution."
        return None

    def get_report(self) -> dict[str, Any]:
        """Returns full structured reliability report."""
        with self._lock:
            items = []
            for name, s in sorted(self._stats.items(), key=lambda x: x[1]["score"]):
                grade = self.get_grade(name)
                items.append(
                    {
                        "tool": name,
                        "score": s["score"],
                        "grade": grade,
                        "calls": s["calls"],
                        "successes": s["successes"],
                        "errors": s["errors"],
                        "consecutive_failures": s["consecutive_failures"],
                        "avg_latency_ms": s["avg_latency_ms"],
                        "last_error": s["last_error"],
                        "recommendation": self.get_recommendation(name),
                    }
                )

        return {
            "total_tracked_tools": len(items),
            "unhealthy_tools_count": sum(1 for i in items if i["grade"] == "F"),
            "tools": items,
        }

    def format_report_text(self) -> str:
        """Formats report for LLM prompt or user inspection."""
        rep = self.get_report()
        lines = [
            f"### TOOL RELIABILITY REPORT ({rep['total_tracked_tools']} tools tracked, {rep['unhealthy_tools_count']} degraded)"
        ]
        if not rep["tools"]:
            lines.append("No tool execution statistics recorded yet.")
            return "\n".join(lines)

        for item in rep["tools"]:
            status = f"[{item['grade']}] ({item['score']:.2f})"
            err_info = f", errors: {item['errors']}/{item['calls']}" if item["errors"] > 0 else ""
            lines.append(f"- **{item['tool']}** {status}: {item['calls']} calls{err_info}")
            if item["recommendation"]:
                lines.append(f"  \u26a0 *{item['recommendation']}*")

        return "\n".join(lines)
