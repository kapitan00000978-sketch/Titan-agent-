"""
Phase 23 — DAG Planner: Decomposes complex user goals into dependency-aware TaskGraphs.
"""
from __future__ import annotations

import json
from typing import Any

from .task_graph import TaskGraph

DAG_PLAN_PROMPT = """You are an expert DAG (Directed Acyclic Graph) Planner.
Decompose the following complex user goal into discrete, dependency-aware task nodes.
Independent tasks that can run in parallel MUST NOT depend on each other.

Departments: engineering, research, operations, quality_security.
Roles: coder, test_writer, reviewer, deployer, researcher, data_validator, hallucination_checker, translator, scheduler_agent, notification_agent, cost_watcher, rate_limiter_agent, security, tester, critic_agent, fallback_agent, performance_optimizer, db_architect.

Goal: {goal}

Output JSON ONLY in this format:
{{
  "nodes": [
    {{
      "id": "node-1",
      "title": "Brief title of the task",
      "department": "engineering",
      "assigned_role": "coder",
      "dependencies": []
    }},
    {{
      "id": "node-2",
      "title": "Another parallel or dependent task",
      "department": "quality_security",
      "assigned_role": "security",
      "dependencies": ["node-1"]
    }}
  ]
}}
"""


class DAGPlanner:
    """Creates and selectively replans TaskGraphs for complex goals."""

    def __init__(self, llm_client: Any | None = None):
        self.llm = llm_client

    async def create_dag_plan(self, goal: str, context: dict[str, Any] | None = None) -> TaskGraph:
        """Create a TaskGraph using LLM if available, or intelligent heuristic decomposition."""
        if self.llm:
            try:
                graph = await self._plan_with_llm(goal, context)
                graph.validate_acyclic()
                return graph
            except (OSError, ValueError, json.JSONDecodeError, RuntimeError):
                pass  # Fall back to heuristic decomposition

        return self._heuristic_decomposition(goal)

    async def _plan_with_llm(self, goal: str, context: dict[str, Any] | None = None) -> TaskGraph:
        prompt = DAG_PLAN_PROMPT.format(goal=goal)
        if context:
            prompt += f"\nAdditional Context:\n{json.dumps(context, default=str)[:2000]}"

        messages = [
            {"role": "system", "content": "You are a DAG planning engine. Respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ]
        resp = await self.llm.chat_completion(messages, temperature=0.2)
        content = resp.content if hasattr(resp, "content") else str(resp)

        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("No valid JSON found in LLM response")

        data = json.loads(content[start : end + 1])
        graph = TaskGraph(goal=goal)

        for item in data.get("nodes", []):
            graph.add_node(
                node_id=str(item.get("id")),
                title=str(item.get("title")),
                department=str(item.get("department", "engineering")),
                assigned_role=str(item.get("assigned_role", "coder")),
                dependencies=item.get("dependencies", []),
            )
        return graph

    def _heuristic_decomposition(self, goal: str) -> TaskGraph:
        """Deterministic heuristic decomposition into a multi-node DAG."""
        graph = TaskGraph(goal=goal)
        g_lower = goal.lower()

        # Check for multiple phases in goal
        has_research = any(k in g_lower for k in ["research", "investigate", "find out", "analyze", "organib"])
        has_code = any(k in g_lower for k in ["code", "implement", "build", "create", "fix", "yoz", "tuz"])
        has_test = any(k in g_lower for k in ["test", "verify", "tekshir", "sinov"])
        has_security = any(k in g_lower for k in ["security", "audit", "xavfsiz", "vuln"])
        has_deploy = any(k in g_lower for k in ["deploy", "notify", "release", "e'lon"])

        node_id_counter = 1

        # Phase 1: Research / Analysis (if requested or complex)
        res_node_id = None
        if has_research or (not has_code and not has_test and not has_security):
            res_node_id = f"node-{node_id_counter}"
            node_id_counter += 1
            graph.add_node(
                node_id=res_node_id,
                title=f"Research & discovery: {goal[:60]}",
                department="research",
                assigned_role="researcher",
                dependencies=[],
            )

        # Phase 2: Implementation (Engineering)
        code_node_id = None
        if has_code or res_node_id is None:
            code_node_id = f"node-{node_id_counter}"
            node_id_counter += 1
            deps = [res_node_id] if res_node_id else []
            graph.add_node(
                node_id=code_node_id,
                title=f"Technical implementation: {goal[:60]}",
                department="engineering",
                assigned_role="coder",
                dependencies=deps,
            )

        # Phase 3: Parallel QA & Security
        qa_node_id = None
        if has_test or code_node_id:
            qa_node_id = f"node-{node_id_counter}"
            node_id_counter += 1
            deps = [code_node_id] if code_node_id else ([res_node_id] if res_node_id else [])
            graph.add_node(
                node_id=qa_node_id,
                title="Verification & automated tests",
                department="engineering",
                assigned_role="test_writer",
                dependencies=deps,
            )

        sec_node_id = None
        if has_security or code_node_id:
            sec_node_id = f"node-{node_id_counter}"
            node_id_counter += 1
            deps = [code_node_id] if code_node_id else ([res_node_id] if res_node_id else [])
            graph.add_node(
                node_id=sec_node_id,
                title="Security audit & vulnerability review",
                department="quality_security",
                assigned_role="security",
                dependencies=deps,
            )

        # Phase 4: Finalization / Operations
        final_deps = [n for n in [qa_node_id, sec_node_id] if n]
        if final_deps or has_deploy:
            final_node_id = f"node-{node_id_counter}"
            title = "Deployment and release sign-off" if has_deploy else "Consolidation & operations sign-off"
            graph.add_node(
                node_id=final_node_id,
                title=title,
                department="operations",
                assigned_role="deployer" if has_deploy else "notification_agent",
                dependencies=final_deps,
            )

        graph.validate_acyclic()
        return graph

    def replan_subgraph(self, graph: TaskGraph, failed_node_id: str, error: str) -> TaskGraph:
        """
        Selective replan: resets only the failed node and its downstream dependents.
        Adapts the failed node title with remediation context.
        """
        if failed_node_id not in graph.nodes:
            return graph

        graph.reset_node_and_dependents(failed_node_id)
        failed_node = graph.nodes[failed_node_id]
        failed_node.metadata["replan_reason"] = error
        failed_node.metadata["previous_error"] = error
        failed_node.title = f"[Remediation] {failed_node.title}"

        return graph
