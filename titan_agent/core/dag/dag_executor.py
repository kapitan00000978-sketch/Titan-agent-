"""
Phase 23 — DAG Executor: Wave-based parallel asynchronous execution of TaskGraphs.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from ...team_leads import BaseTeamLead, build_team_leads
from .task_graph import NodeStatus, TaskGraph, TaskNode


@dataclass
class DAGExecutionResult:
    """Summary of complete DAG execution."""

    goal: str
    success: bool
    total_nodes: int
    completed_nodes: int
    failed_nodes: int
    duration: float
    graph: TaskGraph
    summary: str
    node_results: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "success": self.success,
            "total_nodes": self.total_nodes,
            "completed_nodes": self.completed_nodes,
            "failed_nodes": self.failed_nodes,
            "duration": round(self.duration, 2),
            "summary": self.summary,
            "graph": self.graph.to_dict(),
        }


class DAGExecutor:
    """Executes a TaskGraph in parallel waves respecting dependencies and department leads."""

    def __init__(
        self,
        leads: dict[str, BaseTeamLead] | None = None,
        max_concurrency: int = 4,
    ):
        self.leads = leads or build_team_leads()
        self.max_concurrency = max(1, max_concurrency)

    async def execute_graph(
        self,
        graph: TaskGraph,
        session_id: str = "dag_exec",
        enable_replan: bool = True,
    ) -> DAGExecutionResult:
        """Executes graph wave-by-wave until finished."""
        graph.validate_acyclic()
        start_time = time.time()
        sem = asyncio.Semaphore(self.max_concurrency)

        wave_idx = 1
        while not graph.is_finished():
            ready_nodes = graph.get_ready_nodes()
            if not ready_nodes:
                # Deadlock detection: no nodes ready and graph not finished
                for nid, node in graph.nodes.items():
                    if node.status == NodeStatus.PENDING:
                        node.status = NodeStatus.FAILED
                        node.error = "Deadlock: dependencies could not be resolved or upstream failed."
                break

            # Mark ready nodes as running
            for node in ready_nodes:
                node.status = NodeStatus.RUNNING
                node.start_time = time.time()

            async def run_one(n: TaskNode):
                async with sem:
                    return await self._execute_node(n, session_id=session_id)

            # Parallel wave execution
            await asyncio.gather(*(run_one(n) for n in ready_nodes))
            wave_idx += 1

        duration = time.time() - start_time
        prog = graph.progress()
        is_success = prog["successful"]

        # Build human-readable execution summary
        summary_lines = [
            "# TASK GRAPH (DAG) EXECUTION SUMMARY",
            f"**Goal**: {graph.goal}",
            f"**Status**: {'✅ COMPLETED' if is_success else '❌ FAILED'}",
            f"**Progress**: {prog['completed']}/{prog['total_nodes']} nodes ({prog['percent']}%)",
            f"**Execution Time**: {round(duration, 2)}s",
            "",
            "## Node Outcomes:",
        ]

        for nid in graph.topological_sort():
            node = graph.nodes[nid]
            status_icon = "✅" if node.status == NodeStatus.COMPLETED else "❌"
            summary_lines.append(
                f"- {status_icon} **[{node.id}]** `{node.title}` ({node.department}/{node.assigned_role})"
            )
            if node.error:
                summary_lines.append(f"  *Error*: {node.error}")
            elif node.result:
                preview = node.result[:120].replace("\n", " ") + ("..." if len(node.result) > 120 else "")
                summary_lines.append(f"  *Output*: {preview}")

        return DAGExecutionResult(
            goal=graph.goal,
            success=is_success,
            total_nodes=prog["total_nodes"],
            completed_nodes=prog["completed"],
            failed_nodes=prog["failed"],
            duration=duration,
            graph=graph,
            summary="\n".join(summary_lines),
            node_results={nid: n.to_dict() for nid, n in graph.nodes.items()},
        )

    async def _execute_node(self, node: TaskNode, session_id: str) -> None:
        """Route node to the appropriate department lead and apply verification."""
        lead = self.leads.get(node.department) or self.leads.get("engineering")
        if not lead:
            node.status = NodeStatus.FAILED
            node.error = f"No lead found for department '{node.department}'"
            node.end_time = time.time()
            return

        try:
            lead_result = await lead.execute_task(
                task=node.title,
                role=node.assigned_role,
                session_id=f"{session_id}-{node.id}",
            )

            if lead_result.success:
                node.status = NodeStatus.COMPLETED
                node.result = lead_result.output
                node.end_time = time.time()
            else:
                if node.retry_count < node.max_retries:
                    node.retry_count += 1
                    node.status = NodeStatus.PENDING  # will be retried in next wave
                else:
                    node.status = NodeStatus.FAILED
                    node.error = "; ".join(lead_result.verification_notes) or lead_result.output
                    node.end_time = time.time()
        except Exception as exc:  # noqa: BLE001
            if node.retry_count < node.max_retries:
                node.retry_count += 1
                node.status = NodeStatus.PENDING
            else:
                node.status = NodeStatus.FAILED
                node.error = f"Execution exception: {exc!s}"
                node.end_time = time.time()
