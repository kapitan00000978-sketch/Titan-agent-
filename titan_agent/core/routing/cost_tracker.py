"""
Phase 27 — Genesis Darajasi 7: Cognitive Budget & Token Cost Tracker.

Tracks prompt and completion token expenditures, computes USD pricing per model tier,
and raises warnings or clamps when cost limits are reached.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from .model_router import ModelRouter


class CognitiveBudgetTracker:
    """Thread-safe accounting of token usage and financial cost across LLM models."""

    def __init__(self, budget_limit_usd: float = 10.0):
        self.budget_limit_usd = float(budget_limit_usd)
        self._lock = threading.RLock()
        self._usage_by_model: dict[str, dict[str, Any]] = {}
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._total_cost_usd: float = 0.0

    def record_usage(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Record token usage for a model call and return the incremental USD cost."""
        m_name = str(model_name).lower().strip()
        inp = max(0, int(input_tokens))
        out = max(0, int(output_tokens))

        profile = ModelRouter.DEFAULT_PROFILES.get(m_name)
        if profile:
            cost = (inp * profile.input_cost_per_m + out * profile.output_cost_per_m) / 1_000_000.0
        else:
            # Default fallback rate: $1.00 / 1M input, $3.00 / 1M output
            cost = (inp * 1.00 + out * 3.00) / 1_000_000.0

        with self._lock:
            self._total_input_tokens += inp
            self._total_output_tokens += out
            self._total_cost_usd += cost

            rec = self._usage_by_model.setdefault(
                m_name,
                {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                    "last_call_time": 0.0,
                },
            )
            rec["calls"] += 1
            rec["input_tokens"] += inp
            rec["output_tokens"] += out
            rec["cost_usd"] += cost
            rec["last_call_time"] = time.time()

        return cost

    def is_budget_exceeded(self) -> bool:
        """Checks if total cost exceeds budget limit."""
        with self._lock:
            return self._total_cost_usd >= self.budget_limit_usd

    def get_summary(self) -> dict[str, Any]:
        """Returns structured summary of token and financial usage."""
        with self._lock:
            return {
                "budget_limit_usd": self.budget_limit_usd,
                "total_cost_usd": round(self._total_cost_usd, 5),
                "remaining_budget_usd": round(max(0.0, self.budget_limit_usd - self._total_cost_usd), 5),
                "is_budget_exceeded": self.is_budget_exceeded(),
                "total_input_tokens": self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
                "total_tokens": self._total_input_tokens + self._total_output_tokens,
                "models": {k: dict(v) for k, v in self._usage_by_model.items()},
            }

    def format_status_text(self) -> str:
        """Renders human-readable summary for tools or user inspection."""
        s = self.get_summary()
        pct = (s["total_cost_usd"] / s["budget_limit_usd"] * 100.0) if s["budget_limit_usd"] > 0 else 0.0
        lines = [
            "### COGNITIVE BUDGET & TOKEN USAGE REPORT",
            f"- **Total Spent**: ${s['total_cost_usd']:.4f} / ${s['budget_limit_usd']:.2f} ({pct:.1f}% consumed)",
            f"- **Remaining**: ${s['remaining_budget_usd']:.4f}",
            f"- **Tokens Processed**: {s['total_tokens']:,} (Input: {s['total_input_tokens']:,}, Output: {s['total_output_tokens']:,})",
        ]
        if s["is_budget_exceeded"]:
            lines.append("\u26a0 **BUDGET ALERT: Spending limit reached!**")

        if s["models"]:
            lines.append("\n**Usage by Model**:")
            for m, data in s["models"].items():
                lines.append(
                    f"- `{m}`: {data['calls']} calls, {data['input_tokens'] + data['output_tokens']:,} tokens, ${data['cost_usd']:.4f}"
                )
        else:
            lines.append("\n(No model calls recorded yet)")

        return "\n".join(lines)
