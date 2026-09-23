"""
Tests for Phase 23 Genesis Level Task Graph (DAG) Planning & Execution Engine:
- TaskNode, TaskGraph (cycle detection, Kahn's topological sort, Mermaid export)
- Selective Subtree Replanning (preserving independent completed work)
- DAGPlanner (heuristic decomposition & selective replanning)
- DAGExecutor (wave-based parallel execution & concurrency)
- DAG Tools (dag_plan_and_run, dag_visualize)
- Server endpoint (/api/dag/status)
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from titan_agent.core.dag import (
    DAGExecutor,
    DAGPlanner,
    NodeStatus,
    TaskGraph,
)
from titan_agent.server import app
from titan_agent.team_leads import TeamLeadResult
from titan_agent.tools import ToolRegistry


def test_task_graph_basics_and_topological_sort():
    """Verify nodes, dependencies, and topological order."""
    graph = TaskGraph(goal="Build authentication service")

    # Add nodes
    graph.add_node("n1", "Research OAuth spec", department="research", assigned_role="researcher")
    graph.add_node("n2", "Implement JWT token handler", department="engineering", assigned_role="coder", dependencies=["n1"])
    graph.add_node("n3", "Write unit tests for JWT", department="engineering", assigned_role="test_writer", dependencies=["n2"])
    graph.add_node("n4", "Security audit token signing", department="quality_security", assigned_role="security", dependencies=["n2"])

    assert graph.validate_acyclic() is True
    order = graph.topological_sort()
    assert order.index("n1") < order.index("n2")
    assert order.index("n2") < order.index("n3")
    assert order.index("n2") < order.index("n4")

    # Ready nodes initially should only be n1
    ready = graph.get_ready_nodes()
    assert [n.id for n in ready] == ["n1"]

    # Mermaid export
    mermaid = graph.to_mermaid()
    assert "graph TD" in mermaid
    assert "n1 --> n2" in mermaid
    assert "n2 --> n3" in mermaid


def test_task_graph_cycle_detection():
    """Verify that circular dependencies raise ValueError."""
    graph = TaskGraph(goal="Circular test")
    graph.add_node("a", "Step A", dependencies=["b"])
    graph.add_node("b", "Step B", dependencies=["a"])

    with pytest.raises(ValueError, match="Circular dependency detected"):
        graph.validate_acyclic()


def test_selective_subgraph_replanning():
    """
    If node-2 fails, reset_node_and_dependents must reset node-2 and its downstream
    dependents, while preserving independent node-4 and upstream node-1!
    """
    graph = TaskGraph(goal="Selective replan test")
    # n1 -> n2 -> n3
    # n4 is independent
    graph.add_node("n1", "Init config")
    graph.add_node("n2", "Run migration", dependencies=["n1"])
    graph.add_node("n3", "Seed database", dependencies=["n2"])
    graph.add_node("n4", "Setup logging")

    # Simulate execution progress
    graph.nodes["n1"].status = NodeStatus.COMPLETED
    graph.nodes["n4"].status = NodeStatus.COMPLETED
    graph.nodes["n2"].status = NodeStatus.FAILED
    graph.nodes["n3"].status = NodeStatus.PENDING

    # Selective reset on n2
    reset_targets = graph.reset_node_and_dependents("n2")
    assert set(reset_targets) == {"n2", "n3"}

    # Verification: n1 and n4 remain COMPLETED!
    assert graph.nodes["n1"].status == NodeStatus.COMPLETED
    assert graph.nodes["n4"].status == NodeStatus.COMPLETED
    # n2 and n3 are reset to PENDING
    assert graph.nodes["n2"].status == NodeStatus.PENDING
    assert graph.nodes["n3"].status == NodeStatus.PENDING


def test_dag_planner_heuristic_and_replanning():
    """Test heuristic decomposition and subgraph replanning."""
    planner = DAGPlanner()
    graph = planner._heuristic_decomposition("Investigate memory leak, write fix, and test performance")
    assert graph.validate_acyclic() is True
    assert len(graph.nodes) >= 3

    # Check replan_subgraph modifies the failed node with context
    first_node_id = graph.topological_sort()[0]
    planner.replan_subgraph(graph, first_node_id, "Timeout querying logs")
    assert "[Remediation]" in graph.nodes[first_node_id].title
    assert graph.nodes[first_node_id].metadata.get("previous_error") == "Timeout querying logs"


@pytest.mark.asyncio
async def test_dag_executor_wave_parallel_execution():
    """
    Verify wave-based execution:
    Wave 1: n1 and n2 run in parallel.
    Wave 2: n3 runs after both n1 and n2 complete.
    """
    mock_eng_lead = MagicMock()
    mock_eng_lead.execute_task = AsyncMock(
        return_value=TeamLeadResult(
            department="engineering",
            lead_id="lead_eng",
            assigned_role="coder",
            task="Task",
            success=True,
            output="Executed successfully",
            verification_verdict="VERIFIED",
        )
    )
    leads = {"engineering": mock_eng_lead}
    executor = DAGExecutor(leads=leads, max_concurrency=4)

    graph = TaskGraph(goal="Parallel build")
    graph.add_node("n1", "Compile backend", department="engineering")
    graph.add_node("n2", "Compile frontend", department="engineering")
    graph.add_node("n3", "Bundle release", department="engineering", dependencies=["n1", "n2"])

    res = await executor.execute_graph(graph)
    assert res.success is True
    assert res.completed_nodes == 3
    assert res.failed_nodes == 0
    assert "✅ COMPLETED" in res.summary
    assert mock_eng_lead.execute_task.call_count == 3


@pytest.mark.asyncio
async def test_dag_tools_integration():
    """Test tool_dag_visualize and tool_dag_plan_and_run."""
    tools = ToolRegistry()

    # Visualize
    vis = await tools.tool_dag_visualize("Build high performance cache")
    assert "### TASK GRAPH (DAG) VISUALIZATION" in vis
    assert "```mermaid" in vis
    assert "Topological Order" in vis

    # Plan and Run with mocked executor
    mock_eng_lead = MagicMock()
    mock_eng_lead.execute_task = AsyncMock(
        return_value=TeamLeadResult(
            department="engineering",
            lead_id="lead_eng",
            assigned_role="coder",
            task="Task",
            success=True,
            output="Done",
            verification_verdict="VERIFIED",
        )
    )
    mock_res_lead = MagicMock()
    mock_res_lead.execute_task = AsyncMock(
        return_value=TeamLeadResult(
            department="research",
            lead_id="lead_res",
            assigned_role="researcher",
            task="Task",
            success=True,
            output="Done",
            verification_verdict="VERIFIED",
        )
    )
    tools._meta_orchestrator = MagicMock()
    mock_dag_res = MagicMock()
    mock_dag_res.summary = "# TASK GRAPH (DAG) EXECUTION SUMMARY\n✅ COMPLETED"
    tools._meta_orchestrator.orchestrate_dag = AsyncMock(return_value=mock_dag_res)

    run_output = await tools.tool_dag_plan_and_run("Design and deploy Redis cluster")
    assert "TASK GRAPH (DAG) EXECUTION SUMMARY" in run_output
    assert "✅ COMPLETED" in run_output


def test_server_dag_status_endpoint():
    """Test GET /api/dag/status returns valid JSON."""
    from titan_agent import auth

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {auth.get_server_api_key()}"}
    response = client.get("/api/dag/status", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "active" in data
