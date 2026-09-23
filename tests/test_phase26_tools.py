"""Tests for Phase 26: Dynamic Tool Discovery, Sandboxing & Reliability Rating."""
from titan_agent.core.tools.dynamic_registry import DynamicToolSelector
from titan_agent.core.tools.registry import RiskLevel
from titan_agent.core.tools.reliability import ToolReliabilityTracker
from titan_agent.core.tools.sandboxing import SandboxMode, ToolSandboxGuard
from titan_agent.tools import ToolRegistry


def test_tool_reliability_tracker():
    tracker = ToolReliabilityTracker(alpha=0.4)

    # Initial unobserved score
    assert tracker.get_score("new_tool") == 1.0
    assert tracker.get_grade("new_tool") == "A"
    assert tracker.is_reliable("new_tool")

    # Record 3 failures in a row
    tracker.record_call("flaky_tool", success=False, error="ConnectionTimeout")
    tracker.record_call("flaky_tool", success=False, error="ConnectionTimeout")
    tracker.record_call("flaky_tool", success=False, error="ConnectionTimeout")

    score = tracker.get_score("flaky_tool")
    assert score < 0.55
    grade = tracker.get_grade("flaky_tool")
    assert grade == "F"
    assert not tracker.is_reliable("flaky_tool")

    rec = tracker.get_recommendation("flaky_tool")
    assert rec is not None
    assert "unreliable" in rec.lower()

    # Recovery with consecutive successes
    for _ in range(5):
        tracker.record_call("flaky_tool", success=True, latency_ms=45.0)

    recovered_score = tracker.get_score("flaky_tool")
    assert recovered_score > score
    assert tracker.is_reliable("flaky_tool")

    # Report text
    report_text = tracker.format_report_text()
    assert "TOOL RELIABILITY REPORT" in report_text
    assert "flaky_tool" in report_text


def test_dynamic_tool_selector(tmp_path):
    registry = ToolRegistry(workspace=tmp_path)
    all_defs = registry.get_tool_definitions()
    assert len(all_defs) >= 50

    # 1. Test Sandbox/Docker task
    docker_tools = DynamicToolSelector.select_tools("Run this test suite in an isolated docker sandbox", all_defs, max_tools=15)
    docker_names = {t["function"]["name"] for t in docker_tools}
    # Core tools must be present
    assert "read_file" in docker_names
    assert "execute_command" in docker_names
    # Sandbox domain tools must be selected
    assert "docker_sandbox_run" in docker_names
    assert len(docker_tools) <= 18

    # 2. Test Knowledge Graph task
    kg_tools = DynamicToolSelector.select_tools("Perform impact analysis on this entity using the knowledge graph", all_defs, max_tools=15)
    kg_names = {t["function"]["name"] for t in kg_tools}
    assert any("kg" in name for name in kg_names)

    # 3. Test on-demand Discovery
    matches = DynamicToolSelector.discover_tools("docker", all_defs)
    match_names = [t["function"]["name"] for t in matches]
    assert "docker_sandbox_run" in match_names

    kg_matches = DynamicToolSelector.discover_tools("graph", all_defs, category="knowledge_graph")
    assert len(kg_matches) >= 1
    assert any("kg" in t["function"]["name"] for t in kg_matches)


def test_tool_sandbox_guard():
    # 1. Off mode
    guard_off = ToolSandboxGuard(mode=SandboxMode.OFF)
    allowed, _ = guard_off.check_execution("execute_command", {"command": "rm -rf /"})
    assert allowed

    # 2. Risk classification
    assert guard_off.get_risk_level("execute_command") == RiskLevel.HIGH
    assert guard_off.get_risk_level("write_file") == RiskLevel.MEDIUM
    assert guard_off.get_risk_level("read_file") == RiskLevel.LOW

    # 3. Strict mode
    guard_strict = ToolSandboxGuard(mode=SandboxMode.STRICT)
    allowed, msg = guard_strict.check_execution("execute_command", {"command": "dir"})
    assert not allowed
    assert "SANDBOX STRICT" in msg

    allowed_confirmed, _ = guard_strict.check_execution("execute_command", {"command": "dir", "confirmed": True})
    assert allowed_confirmed

    # 4. Docker mode
    guard_docker = ToolSandboxGuard(mode=SandboxMode.DOCKER)
    allowed, msg = guard_docker.check_execution("execute_command", {"command": "python script.py"})
    assert not allowed
    assert "SANDBOX DOCKER" in msg


def test_tools_integration_discover_and_report(tmp_path):
    registry = ToolRegistry(workspace=tmp_path)

    # Test tool_discover
    res = registry.tool_discover("knowledge graph")
    assert "DISCOVERED TOOLS" in res
    assert "kg_" in res

    # Test tool_reliability_report
    rep = registry.tool_reliability_report()
    assert "TOOL RELIABILITY REPORT" in rep
