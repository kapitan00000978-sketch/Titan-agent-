"""Tests for Phase 29: Quality Drift Detection & Degradation Monitoring."""

import tempfile
from pathlib import Path

import pytest

from titan_agent.core.monitoring import (
    QualityDriftDetector,
    TaskExecutionMetric,
)
from titan_agent.tools import ToolRegistry


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestTaskExecutionMetric:
    def test_metric_serialization(self):
        m = TaskExecutionMetric(
            task_id="t-001",
            category="coding",
            success=False,
            steps=7,
            duration_sec=12.4,
            tokens_used=1500,
            failed_tools=["edit_file", "execute_command"],
            error="SyntaxError",
        )
        d = m.to_dict()
        assert d["task_id"] == "t-001"
        assert d["success"] is False
        assert len(d["failed_tools"]) == 2

        restored = TaskExecutionMetric.from_dict(d)
        assert restored.task_id == m.task_id
        assert restored.failed_tools == m.failed_tools
        assert restored.steps == 7


class TestQualityDriftDetector:
    def test_insufficient_history_returns_normal(self, temp_workspace: Path):
        detector = QualityDriftDetector()
        detector.record_task("t-1", success=True)
        detector.record_task("t-2", success=True)

        report = detector.check_drift(window_size=10)
        assert report.drift_detected is False
        assert report.alert_level == "NORMAL"
        assert "Insufficient history" in report.root_cause_analysis

    def test_stable_performance_no_drift(self, temp_workspace: Path):
        detector = QualityDriftDetector()
        # 15 successful tasks baseline
        for i in range(15):
            detector.record_task(f"base-{i}", success=True, steps=2, duration_sec=1.5)

        # 10 successful tasks in current window
        for i in range(10):
            detector.record_task(f"cur-{i}", success=True, steps=2, duration_sec=1.6)

        report = detector.check_drift(window_size=10, baseline_size=15)
        assert report.drift_detected is False
        assert report.alert_level == "NORMAL"
        assert report.success_rate_drop == 0.0
        assert report.current_success_rate == 1.0

    def test_severe_regression_triggers_critical_drift(self, temp_workspace: Path):
        detector = QualityDriftDetector()
        # Baseline: 15 tasks, all succeed
        for i in range(15):
            detector.record_task(f"base-{i}", success=True, steps=2, duration_sec=2.0)

        # Current window: 10 tasks, 8 fail with tool errors
        for i in range(10):
            succ = (i < 2)  # only 2 succeed
            detector.record_task(
                f"cur-{i}",
                success=succ,
                steps=6,
                duration_sec=5.0,
                failed_tools=["docker_sandbox_run", "ast_patch_file"] if not succ else [],
            )

        report = detector.check_drift(window_size=10, baseline_size=15, threshold_drop=0.20)
        assert report.drift_detected is True
        assert report.alert_level == "CRITICAL"
        assert report.success_rate_drop >= 0.70
        assert len(report.problematic_tools) >= 1
        assert report.problematic_tools[0][0] in ["docker_sandbox_run", "ast_patch_file"]
        assert len(report.remediation_suggestions) > 0

    def test_step_inflation_triggers_warning_drift(self, temp_workspace: Path):
        detector = QualityDriftDetector()
        # Baseline: 15 tasks, steps avg = 2
        for i in range(15):
            detector.record_task(f"base-{i}", success=True, steps=2)

        # Current: 10 tasks, success maintained but steps avg = 5 (2.5x inflation)
        for i in range(10):
            detector.record_task(f"cur-{i}", success=True, steps=5)

        report = detector.check_drift(window_size=10, baseline_size=15)
        assert report.drift_detected is True
        assert report.alert_level in ["WARNING", "CRITICAL"]
        assert report.step_inflation_ratio >= 2.0
        assert any("DAG" in s for s in report.remediation_suggestions)

    def test_persistence_save_and_load(self, temp_workspace: Path):
        storage_file = temp_workspace / "telemetry.json"
        detector1 = QualityDriftDetector(storage_path=storage_file)
        for i in range(5):
            detector1.record_task(f"t-{i}", success=True, steps=i + 1)

        assert storage_file.exists()

        detector2 = QualityDriftDetector(storage_path=storage_file)
        assert len(detector2.get_metrics()) == 5
        assert detector2.get_metrics()[2].steps == 3


class TestToolRegistryDriftIntegration:
    def test_drift_tools_registered_in_definitions(self, temp_workspace: Path):
        tools = ToolRegistry(temp_workspace)
        defs = tools.get_tool_definitions()
        names = [d.get("function", {}).get("name") for d in defs]
        assert "drift_record_task" in names
        assert "drift_check" in names
        assert "drift_status" in names

    def test_tool_drift_record_and_status(self, temp_workspace: Path):
        tools = ToolRegistry(temp_workspace)
        rec_res = tools.tool_drift_record_task(
            task_id="task_alpha_1",
            success=True,
            steps=3,
            duration_sec=2.5,
            tokens_used=450,
            category="refactoring",
        )
        assert "DRIFT TELEMETRY RECORDED" in rec_res
        assert "task_alpha_1" in rec_res
        assert "SUCCESS" in rec_res

        status_res = tools.tool_drift_status()
        assert "DRIFT TELEMETRY STATUS" in status_res
        assert "task_alpha_1" in status_res
        assert "100.0%" in status_res

    def test_tool_drift_check(self, temp_workspace: Path):
        tools = ToolRegistry(temp_workspace)
        # Record tasks
        for i in range(12):
            tools.tool_drift_record_task(f"run_{i}", success=(i % 2 == 0), steps=2)

        check_res = tools.tool_drift_check(window_size=5)
        assert "PERFORMANCE DRIFT REPORT" in check_res
        assert "Sample Size" in check_res
