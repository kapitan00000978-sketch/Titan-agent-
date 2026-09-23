"""
Phase 22 — Level 1: Meta-Orchestrator (Chief Agent / Bosh Miya).

The single permanent 'Chief' agent that sits at the top of the Titan Genesis hierarchy.
It receives high-level user directives and manages:
1. GlobalGoalMemory — Maintains project direction, milestones, and cross-session memory.
2. ResourceBudget — Allocates and monitors token, step, and execution limits across teams.
3. DepartmentDispatcher — Decides which Team Lead(s) execute the task.
4. ConflictResolver — Arbitrates conflicting recommendations between departments (e.g.
   Engineering wants fast merge vs Quality/Security flags caution).
5. Executive Synthesis — Compiles departmental deliverables into a unified final briefing.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .core.dag import DAGExecutionResult, DAGExecutor, DAGPlanner
from .team_leads import (
    BaseTeamLead,
    TeamLeadResult,
    build_team_leads,
    route_to_department,
)


@dataclass
class GlobalMilestone:
    id: str
    title: str
    status: str = "pending"  # "pending", "in_progress", "completed", "failed"
    assigned_department: str = "engineering"
    notes: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class GlobalGoalMemory:
    """Maintains overarching project direction across sessions."""

    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self.project_goal: str = ""
        self.active_goals: list[str] = []
        self.milestones: list[GlobalMilestone] = []
        if self.storage_path and self.storage_path.exists():
            self.load()

    def set_project_goal(self, goal: str) -> None:
        self.project_goal = goal
        if goal and goal not in self.active_goals:
            self.active_goals.append(goal)
        self.save()

    def add_milestone(self, mid: str, title: str, department: str = "engineering") -> GlobalMilestone:
        m = GlobalMilestone(id=mid, title=title, assigned_department=department)
        self.milestones.append(m)
        self.save()
        return m

    def complete_milestone(self, mid: str, notes: str = "") -> bool:
        for m in self.milestones:
            if m.id == mid:
                m.status = "completed"
                m.notes = notes
                m.updated_at = time.time()
                self.save()
                return True
        return False

    def save(self) -> None:
        if not self.storage_path:
            return
        data = {
            "project_goal": self.project_goal,
            "active_goals": self.active_goals,
            "milestones": [
                {
                    "id": m.id,
                    "title": m.title,
                    "status": m.status,
                    "assigned_department": m.assigned_department,
                    "notes": m.notes,
                    "created_at": m.created_at,
                    "updated_at": m.updated_at,
                }
                for m in self.milestones
            ],
        }
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            self.project_goal = data.get("project_goal", "")
            self.active_goals = data.get("active_goals", [])
            self.milestones = [
                GlobalMilestone(
                    id=m["id"],
                    title=m["title"],
                    status=m.get("status", "pending"),
                    assigned_department=m.get("assigned_department", "engineering"),
                    notes=m.get("notes", ""),
                    created_at=m.get("created_at", time.time()),
                    updated_at=m.get("updated_at", time.time()),
                )
                for m in data.get("milestones", [])
            ]
        except (OSError, json.JSONDecodeError, KeyError):
            pass


class ResourceBudget:
    """Tracks token and step budgets per department."""

    def __init__(self, max_tokens: int = 200_000, max_steps: int = 50):
        self.max_tokens = max_tokens
        self.max_steps = max_steps
        self.spent_tokens: dict[str, int] = {
            "engineering": 0,
            "research": 0,
            "operations": 0,
            "quality_security": 0,
            "orchestrator": 0,
        }
        self.spent_steps: dict[str, int] = {
            "engineering": 0,
            "research": 0,
            "operations": 0,
            "quality_security": 0,
            "orchestrator": 0,
        }

    def record_usage(self, department: str, tokens: int = 0, steps: int = 1) -> None:
        dep = department.lower()
        self.spent_tokens[dep] = self.spent_tokens.get(dep, 0) + tokens
        self.spent_steps[dep] = self.spent_steps.get(dep, 0) + steps

    def total_tokens(self) -> int:
        return sum(self.spent_tokens.values())

    def total_steps(self) -> int:
        return sum(self.spent_steps.values())

    def is_exhausted(self) -> bool:
        return self.total_tokens() >= self.max_tokens or self.total_steps() >= self.max_steps

    def summary(self) -> dict[str, Any]:
        return {
            "total_tokens_spent": self.total_tokens(),
            "max_tokens": self.max_tokens,
            "total_steps_spent": self.total_steps(),
            "max_steps": self.max_steps,
            "exhausted": self.is_exhausted(),
            "breakdown_tokens": dict(self.spent_tokens),
            "breakdown_steps": dict(self.spent_steps),
        }


class ConflictResolver:
    """
    Arbitrates conflicts across departments.
    For instance: Engineering reports 'ready' while Quality/Security flags 'SECURITY_BLOCKER'.
    """

    @staticmethod
    def arbitrate(results: list[TeamLeadResult]) -> tuple[str, str]:
        """
        Returns:
            verdict: "APPROVED", "REMEDIATE", "REJECTED"
            rationale: Summary explanation of the arbitration decision.
        """
        has_security_blocker = any(
            r.department == "quality_security" and r.verification_verdict == "SECURITY_BLOCKER"
            for r in results
        )
        has_failure = any(not r.success for r in results)
        has_recs = any(r.verification_verdict == "CHANGES_RECOMMENDED" for r in results)

        if has_security_blocker:
            return (
                "REMEDIATE",
                "Arbitration: Quality/Security department identified critical blockers. Security overrides engineering; remediation is required before approval.",
            )
        if has_failure:
            return (
                "REMEDIATE",
                "Arbitration: One or more departmental deliverables failed execution or verification. Remediation required.",
            )
        if has_recs:
            return (
                "APPROVED_WITH_CONDITIONS",
                "Arbitration: Deliverables approved with recommended changes from department review.",
            )
        return (
            "APPROVED",
            "Arbitration: All departmental leads verified deliverables successfully. Full approval granted.",
        )


@dataclass
class OrchestrationResult:
    """Master response produced by Meta-Orchestrator."""

    goal: str
    success: bool
    final_verdict: str
    synthesis: str
    department_results: dict[str, TeamLeadResult] = field(default_factory=dict)
    arbitration_rationale: str = ""
    budget_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "success": self.success,
            "final_verdict": self.final_verdict,
            "arbitration_rationale": self.arbitration_rationale,
            "synthesis": self.synthesis,
            "departments": {
                k: v.to_dict() for k, v in self.department_results.items()
            },
            "budget": self.budget_summary,
        }


class MetaOrchestrator:
    """Chief Agent (Level 1) of the Titan Genesis architecture."""

    def __init__(
        self,
        leads: dict[str, BaseTeamLead] | None = None,
        goal_memory: GlobalGoalMemory | None = None,
        budget: ResourceBudget | None = None,
        dag_planner: DAGPlanner | None = None,
        dag_executor: DAGExecutor | None = None,
    ):
        self.leads = leads or build_team_leads()
        self.goal_memory = goal_memory or GlobalGoalMemory()
        self.budget = budget or ResourceBudget()
        self.conflict_resolver = ConflictResolver()
        self.dag_planner = dag_planner or DAGPlanner()
        self.dag_executor = dag_executor or DAGExecutor(leads=self.leads)

    async def orchestrate(
        self,
        goal: str,
        departments: list[str] | None = None,
        session_id: str = "meta_session",
        opts: dict[str, Any] | None = None,
    ) -> OrchestrationResult:
        """
        Execute high-level user goal through the hierarchical chain:
        1. Remember global goal
        2. Determine target department(s)
        3. Dispatch to department leads
        4. Gather results & lead-level verification
        5. Arbitrate conflicts
        6. Synthesize executive summary
        """
        self.goal_memory.set_project_goal(goal)
        self.budget.record_usage("orchestrator", tokens=100, steps=1)

        # 1. Routing
        if not departments:
            primary_dep = route_to_department(goal)
            target_deps = [primary_dep]
            # If goal involves code, also bring in quality_security for double verification
            if primary_dep == "engineering" and any(k in goal.lower() for k in ["secure", "prod", "critical", "release"]):
                target_deps.append("quality_security")
        else:
            target_deps = [d.lower() for d in departments if d.lower() in self.leads]

        if not target_deps:
            target_deps = ["engineering"]

        # 2. Dispatch to Team Leads
        dep_results: dict[str, TeamLeadResult] = {}
        for dep in target_deps:
            if self.budget.is_exhausted():
                break

            lead = self.leads.get(dep)
            if not lead:
                continue

            self.budget.record_usage(dep, tokens=500, steps=1)
            result = await lead.execute_task(
                task=goal,
                session_id=session_id,
                opts=opts,
            )
            dep_results[dep] = result

        # 3. Arbitration
        verdict, rationale = self.conflict_resolver.arbitrate(list(dep_results.values()))
        is_success = verdict in ("APPROVED", "APPROVED_WITH_CONDITIONS")

        # 4. Executive Synthesis
        synthesis_lines = [
            "# TITAN META-ORCHESTRATOR EXECUTIVE REPORT",
            f"**Goal**: {goal}",
            f"**Verdict**: {verdict}",
            f"**Arbitration**: {rationale}",
            "",
            "## Department Deliverables:",
        ]

        for dep, res in dep_results.items():
            synthesis_lines.append(f"### Bo'lim: {res.department.upper()} (Lead: {res.lead_id})")
            synthesis_lines.append(f"- **Assigned Worker**: {res.assigned_role}")
            synthesis_lines.append(f"- **Status**: {'OK' if res.success else 'FAILED'}")
            synthesis_lines.append(f"- **Lead Filter Verdict**: {res.verification_verdict}")
            if res.verification_notes:
                synthesis_lines.append(f"- **Verification Notes**: {', '.join(res.verification_notes)}")
            synthesis_lines.append(f"- **Output**:\n{res.output}\n")

        synthesis_text = "\n".join(synthesis_lines)

        return OrchestrationResult(
            goal=goal,
            success=is_success,
            final_verdict=verdict,
            synthesis=synthesis_text,
            department_results=dep_results,
            arbitration_rationale=rationale,
            budget_summary=self.budget.summary(),
        )

    async def orchestrate_dag(
        self,
        goal: str,
        session_id: str = "meta_dag_session",
    ) -> DAGExecutionResult:
        """Execute a complex goal using a Directed Acyclic Graph (DAG) with parallel execution."""
        self.goal_memory.set_project_goal(goal)
        self.budget.record_usage("orchestrator", tokens=150, steps=1)

        graph = await self.dag_planner.create_dag_plan(goal)
        for nid, node in graph.nodes.items():
            self.goal_memory.add_milestone(mid=nid, title=node.title, department=node.department)

        result = await self.dag_executor.execute_graph(graph, session_id=session_id)

        for nid, node in result.graph.nodes.items():
            if node.status.value == "completed":
                self.goal_memory.complete_milestone(mid=nid, notes=node.result[:100] if node.result else "")

        return result
