"""
Phase 23 — Task Graph (DAG): Directed Acyclic Graph data structure for long-term planning.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskNode:
    """A single discrete node within the execution DAG."""

    id: str
    title: str
    department: str = "engineering"
    assigned_role: str = "coder"
    dependencies: set[str] = field(default_factory=set)
    status: NodeStatus = NodeStatus.PENDING
    result: str = ""
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 2
    start_time: float = 0.0
    end_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "department": self.department,
            "assigned_role": self.assigned_role,
            "dependencies": sorted(self.dependencies),
            "status": self.status.value if isinstance(self.status, NodeStatus) else str(self.status),
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "duration": round(self.end_time - self.start_time, 2) if self.end_time > self.start_time else 0.0,
            "metadata": self.metadata,
        }


class TaskGraph:
    """Directed Acyclic Graph (DAG) for tasks, execution order, and selective replanning."""

    def __init__(self, goal: str = ""):
        self.goal = goal
        self.nodes: dict[str, TaskNode] = {}
        self.created_at: float = time.time()

    def add_node(
        self,
        node_id: str,
        title: str,
        department: str = "engineering",
        assigned_role: str = "coder",
        dependencies: list[str] | set[str] | None = None,
        max_retries: int = 2,
    ) -> TaskNode:
        """Add a new node to the DAG."""
        deps = set(dependencies or [])
        node = TaskNode(
            id=node_id,
            title=title,
            department=department,
            assigned_role=assigned_role,
            dependencies=deps,
            max_retries=max_retries,
        )
        self.nodes[node_id] = node
        return node

    def add_dependency(self, target_node_id: str, depends_on_node_id: str) -> None:
        """Add dependency: target_node_id requires depends_on_node_id to be completed first."""
        if target_node_id not in self.nodes:
            raise KeyError(f"Target node '{target_node_id}' does not exist in graph")
        if depends_on_node_id not in self.nodes:
            raise KeyError(f"Dependency node '{depends_on_node_id}' does not exist in graph")
        self.nodes[target_node_id].dependencies.add(depends_on_node_id)

    def validate_acyclic(self) -> bool:
        """
        Validates that the graph has no circular dependencies using Kahn's algorithm.
        Returns True if acyclic, raises ValueError if a cycle is found.
        """
        # Calculate in-degree for each node
        in_degree: dict[str, int] = {nid: len(node.dependencies) for nid, node in self.nodes.items()}
        # Adjacency list: parent -> list of children that depend on parent
        dependents: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        for nid, node in self.nodes.items():
            for dep in node.dependencies:
                if dep in dependents:
                    dependents[dep].append(nid)

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            curr = queue.popleft()
            visited_count += 1
            for child in dependents.get(curr, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if visited_count != len(self.nodes):
            cycle_nodes = [nid for nid, deg in in_degree.items() if deg > 0]
            raise ValueError(f"Circular dependency detected involving nodes: {cycle_nodes}")
        return True

    def topological_sort(self) -> list[str]:
        """Returns topological ordering of node IDs."""
        self.validate_acyclic()
        in_degree: dict[str, int] = {nid: len(node.dependencies) for nid, node in self.nodes.items()}
        dependents: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        for nid, node in self.nodes.items():
            for dep in node.dependencies:
                if dep in dependents:
                    dependents[dep].append(nid)

        queue = deque(sorted([nid for nid, deg in in_degree.items() if deg == 0]))
        order = []

        while queue:
            curr = queue.popleft()
            order.append(curr)
            for child in sorted(dependents.get(curr, [])):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        return order

    def get_ready_nodes(self) -> list[TaskNode]:
        """Find nodes whose dependencies are all COMPLETED and whose status is PENDING."""
        ready = []
        for node in self.nodes.values():
            if node.status != NodeStatus.PENDING:
                continue
            deps_ok = all(
                self.nodes[dep].status == NodeStatus.COMPLETED
                for dep in node.dependencies
                if dep in self.nodes
            )
            if deps_ok:
                ready.append(node)
        return ready

    def get_downstream_nodes(self, node_id: str) -> list[str]:
        """Find all nodes that transitively depend on node_id (for selective replanning)."""
        downstream: list[str] = []
        queue = deque([node_id])
        visited = {node_id}

        while queue:
            curr = queue.popleft()
            for nid, node in self.nodes.items():
                if curr in node.dependencies and nid not in visited:
                    visited.add(nid)
                    downstream.append(nid)
                    queue.append(nid)

        return downstream

    def reset_node_and_dependents(self, node_id: str) -> list[str]:
        """
        Selective replan reset: resets the failed node and all its downstream dependents
        back to PENDING, keeping independent completed nodes untouched.
        """
        targets = [node_id] + self.get_downstream_nodes(node_id)
        for tid in targets:
            if tid in self.nodes:
                n = self.nodes[tid]
                n.status = NodeStatus.PENDING
                n.result = ""
                n.error = None
                n.retry_count = 0
        return targets

    def is_finished(self) -> bool:
        """Returns True if no nodes remain pending or running."""
        return all(
            node.status in (NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED)
            for node in self.nodes.values()
        )

    def is_successful(self) -> bool:
        """Returns True if all nodes completed successfully."""
        return bool(self.nodes) and all(node.status == NodeStatus.COMPLETED for node in self.nodes.values())

    def progress(self) -> dict[str, Any]:
        """Summary of current execution progress."""
        total = len(self.nodes)
        completed = sum(1 for n in self.nodes.values() if n.status == NodeStatus.COMPLETED)
        running = sum(1 for n in self.nodes.values() if n.status == NodeStatus.RUNNING)
        failed = sum(1 for n in self.nodes.values() if n.status == NodeStatus.FAILED)
        pending = sum(1 for n in self.nodes.values() if n.status == NodeStatus.PENDING)
        pct = round((completed / total) * 100, 1) if total > 0 else 0.0

        return {
            "total_nodes": total,
            "completed": completed,
            "running": running,
            "failed": failed,
            "pending": pending,
            "percent": pct,
            "finished": self.is_finished(),
            "successful": self.is_successful(),
        }

    def to_mermaid(self) -> str:
        """Generates a Mermaid graph TD diagram representation."""
        lines = ["graph TD"]
        for nid, node in self.nodes.items():
            status_symbol = {
                NodeStatus.COMPLETED: "✅ ",
                NodeStatus.RUNNING: "⏳ ",
                NodeStatus.FAILED: "❌ ",
                NodeStatus.PENDING: "⏸️ ",
                NodeStatus.SKIPPED: "⏭️ ",
            }.get(node.status, "")
            label = f"{status_symbol}[{node.department.upper()}] {node.title}"
            clean_label = label.replace('"', "'")
            lines.append(f'    {nid}["{clean_label}"]')

        for nid, node in self.nodes.items():
            for dep in sorted(node.dependencies):
                lines.append(f"    {dep} --> {nid}")

        # Color styles
        for nid, node in self.nodes.items():
            if node.status == NodeStatus.COMPLETED:
                lines.append(f"    style {nid} fill:#d4edda,stroke:#28a745,stroke-width:2px")
            elif node.status == NodeStatus.FAILED:
                lines.append(f"    style {nid} fill:#f8d7da,stroke:#dc3545,stroke-width:2px")
            elif node.status == NodeStatus.RUNNING:
                lines.append(f"    style {nid} fill:#fff3cd,stroke:#ffc107,stroke-width:2px")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "created_at": self.created_at,
            "progress": self.progress(),
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
        }
