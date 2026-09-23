"""
Phase 29 — Genesis Darajasi 9: Drift Detection & Quality Degradation Detection.

Monitors agent task execution health over time, detecting regressions in success rates,
anomalous step inflation, execution latencies, and tool failure clusters.
"""
from __future__ import annotations

import datetime
import json
import threading
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TaskExecutionMetric:
    """Record of a single task execution for longitudinal monitoring."""

    task_id: str
    timestamp: float = field(default_factory=time.time)
    category: str = "general"
    success: bool = True
    steps: int = 1
    duration_sec: float = 1.0
    tokens_used: int = 0
    failed_tools: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskExecutionMetric:
        return cls(
            task_id=str(data.get("task_id", "")),
            timestamp=float(data.get("timestamp", time.time())),
            category=str(data.get("category", "general")),
            success=bool(data.get("success", True)),
            steps=int(data.get("steps", 1)),
            duration_sec=float(data.get("duration_sec", 1.0)),
            tokens_used=int(data.get("tokens_used", 0)),
            failed_tools=list(data.get("failed_tools", [])),
            error=data.get("error"),
        )


@dataclass
class DriftReport:
    """Diagnostic report on agent performance health and degradation drift."""

    drift_detected: bool
    alert_level: str  # NORMAL, WARNING, CRITICAL
    baseline_count: int
    current_count: int
    baseline_success_rate: float
    current_success_rate: float
    success_rate_drop: float
    baseline_avg_steps: float
    current_avg_steps: float
    step_inflation_ratio: float
    baseline_avg_duration: float
    current_avg_duration: float
    problematic_tools: list[tuple[str, int]]
    root_cause_analysis: str
    remediation_suggestions: list[str]

    def format_report_text(self) -> str:
        lines = [
            f"### PERFORMANCE DRIFT REPORT [{self.alert_level}]",
            f"- **Drift Detected**: {self.drift_detected}",
            f"- **Sample Size**: Current Window={self.current_count}, Baseline={self.baseline_count}",
            f"- **Success Rate**: Current={self.current_success_rate * 100:.1f}% vs Baseline={self.baseline_success_rate * 100:.1f}% (Drop: {self.success_rate_drop * 100:.1f}%)",
            f"- **Steps Inflation**: Current Avg={self.current_avg_steps:.1f} vs Baseline Avg={self.baseline_avg_steps:.1f} (Ratio: {self.step_inflation_ratio:.2f}x)",
            f"- **Avg Latency**: Current={self.current_avg_duration:.2f}s vs Baseline={self.baseline_avg_duration:.2f}s",
        ]
        if self.problematic_tools:
            tools_str = ", ".join(f"`{t}` ({c} fails)" for t, c in self.problematic_tools)
            lines.append(f"- **Problematic Tools**: {tools_str}")

        lines.append(f"- **Root Cause Diagnosis**: {self.root_cause_analysis}")

        if self.remediation_suggestions:
            lines.append("- **Remediation Suggestions**:")
            for sug in self.remediation_suggestions:
                lines.append(f"  • {sug}")

        return "\n".join(lines)


class QualityDriftDetector:
    """
    Longitudinal performance tracking and statistical regression detector.
    Detects quality degradation by comparing sliding windows against baselines.
    """

    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = Path(storage_path).resolve() if storage_path else None
        self._lock = threading.RLock()
        self._metrics: list[TaskExecutionMetric] = []
        if self.storage_path and self.storage_path.exists():
            self.load_from_disk()

    def record_metric(self, metric: TaskExecutionMetric) -> None:
        """Records an execution metric with thread safety and automatic disk persistence."""
        with self._lock:
            self._metrics.append(metric)
            if self.storage_path:
                self.save_to_disk()

    def record_task(
        self,
        task_id: str,
        success: bool,
        steps: int = 1,
        duration_sec: float = 1.0,
        tokens_used: int = 0,
        failed_tools: list[str] | None = None,
        category: str = "general",
        error: str | None = None,
    ) -> TaskExecutionMetric:
        """Helper to create and record a metric in a single step."""
        metric = TaskExecutionMetric(
            task_id=task_id,
            timestamp=time.time(),
            category=category,
            success=success,
            steps=max(1, int(steps)),
            duration_sec=max(0.01, float(duration_sec)),
            tokens_used=max(0, int(tokens_used)),
            failed_tools=list(failed_tools or []),
            error=error,
        )
        self.record_metric(metric)
        return metric

    def get_metrics(self) -> list[TaskExecutionMetric]:
        """Returns a snapshot copy of all recorded metrics."""
        with self._lock:
            return list(self._metrics)

    def clear(self) -> None:
        """Clears all recorded metrics."""
        with self._lock:
            self._metrics.clear()
            if self.storage_path and self.storage_path.exists():
                try:
                    self.storage_path.unlink()
                except OSError:
                    pass

    def check_drift(
        self,
        window_size: int = 10,
        baseline_size: int = 20,
        threshold_drop: float = 0.20,
    ) -> DriftReport:
        """
        Analyzes performance history for drift.
        Compares the latest `window_size` tasks against the preceding `baseline_size` tasks.
        """
        with self._lock:
            total = len(self._metrics)
            w_size = max(3, int(window_size))
            b_size = max(3, int(baseline_size))

            if total < w_size:
                # Not enough data for meaningful comparative drift detection
                cur_success = (
                    sum(1 for m in self._metrics if m.success) / total
                    if total > 0
                    else 1.0
                )
                return DriftReport(
                    drift_detected=False,
                    alert_level="NORMAL",
                    baseline_count=0,
                    current_count=total,
                    baseline_success_rate=1.0,
                    current_success_rate=cur_success,
                    success_rate_drop=0.0,
                    baseline_avg_steps=1.0,
                    current_avg_steps=sum(m.steps for m in self._metrics) / total if total > 0 else 1.0,
                    step_inflation_ratio=1.0,
                    baseline_avg_duration=1.0,
                    current_avg_duration=sum(m.duration_sec for m in self._metrics) / total if total > 0 else 1.0,
                    problematic_tools=[],
                    root_cause_analysis=f"Insufficient history for drift detection ({total}/{w_size} required). Baseline initializing.",
                    remediation_suggestions=["Continue running tasks to establish statistical baseline."],
                )

            current_window = self._metrics[-w_size:]
            preceding = self._metrics[:-w_size]

            if preceding:
                baseline_window = preceding[-b_size:]
            else:
                # Fallback: if total == w_size, split in half
                half = total // 2
                baseline_window = self._metrics[:half]
                current_window = self._metrics[half:]

            cur_count = len(current_window)
            base_count = len(baseline_window)

            base_success = sum(1 for m in baseline_window if m.success) / base_count
            cur_success = sum(1 for m in current_window if m.success) / cur_count
            success_drop = max(0.0, base_success - cur_success)

            base_steps = sum(m.steps for m in baseline_window) / base_count
            cur_steps = sum(m.steps for m in current_window) / cur_count
            step_inflation = round(cur_steps / max(1.0, base_steps), 2)

            base_dur = sum(m.duration_sec for m in baseline_window) / base_count
            cur_dur = sum(m.duration_sec for m in current_window) / cur_count

            # Analyze problematic tools in current window
            failed_tool_counter: Counter[str] = Counter()
            for m in current_window:
                for t in m.failed_tools:
                    failed_tool_counter[t] += 1
            top_problematic = failed_tool_counter.most_common(5)

            # Determine alert level and drift
            drift_detected = False
            alert_level = "NORMAL"
            suggestions: list[str] = []
            causes: list[str] = []

            if success_drop >= 0.35 or (cur_success < 0.50 and base_success >= 0.70):
                drift_detected = True
                alert_level = "CRITICAL"
                causes.append(f"Severe success rate collapse: dropped by {success_drop * 100:.1f}%.")
            elif success_drop >= threshold_drop or step_inflation >= 1.8:
                drift_detected = True
                alert_level = "WARNING"
                if success_drop >= threshold_drop:
                    causes.append(f"Notable success rate decline: dropped by {success_drop * 100:.1f}%.")
                if step_inflation >= 1.8:
                    causes.append(f"Severe step inflation: tasks taking {step_inflation:.1f}x more steps than baseline.")

            if not drift_detected:
                root_cause = "Agent performance is stable within healthy operational tolerances."
            else:
                if top_problematic:
                    most_failed = top_problematic[0][0]
                    causes.append(f"Tool `{most_failed}` generated the highest failure frequency ({top_problematic[0][1]} failures).")
                    suggestions.append(f"Inspect configuration or schema of `{most_failed}`; check ToolReliabilityTracker recommendations.")
                if step_inflation >= 1.5:
                    suggestions.append("Switch complex workflows to DAG task planner to avoid serial exploratory drift.")
                if cur_success < 0.70:
                    suggestions.append("Promote default LLM routing tier from FAST_CHEAP to STANDARD_CODING or DEEP_REASONING.")
                suggestions.append("Consider running self-healing loop or clearing noisy intermediate workspace state.")
                root_cause = " | ".join(causes)

            return DriftReport(
                drift_detected=drift_detected,
                alert_level=alert_level,
                baseline_count=base_count,
                current_count=cur_count,
                baseline_success_rate=round(base_success, 3),
                current_success_rate=round(cur_success, 3),
                success_rate_drop=round(success_drop, 3),
                baseline_avg_steps=round(base_steps, 2),
                current_avg_steps=round(cur_steps, 2),
                step_inflation_ratio=step_inflation,
                baseline_avg_duration=round(base_dur, 2),
                current_avg_duration=round(cur_dur, 2),
                problematic_tools=top_problematic,
                root_cause_analysis=root_cause,
                remediation_suggestions=suggestions,
            )

    def save_to_disk(self) -> None:
        """Persists all metrics to disk as JSON."""
        if not self.storage_path:
            return
        with self._lock:
            try:
                self.storage_path.parent.mkdir(parents=True, exist_ok=True)
                data = {
                    "updated_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
                    "total_metrics": len(self._metrics),
                    "metrics": [m.to_dict() for m in self._metrics[-500:]],  # keep last 500
                }
                self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except OSError:
                pass

    def load_from_disk(self) -> None:
        """Loads metrics from disk JSON file."""
        if not self.storage_path or not self.storage_path.exists():
            return
        with self._lock:
            try:
                content = self.storage_path.read_text(encoding="utf-8")
                raw = json.loads(content)
                metrics_list = raw.get("metrics", [])
                self._metrics = [TaskExecutionMetric.from_dict(m) for m in metrics_list]
            except (json.JSONDecodeError, OSError):
                pass
