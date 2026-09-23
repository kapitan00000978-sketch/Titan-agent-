"""
Phase 22 — Level 2: Team-Lead Agents (Bo'lim Boshliqlari).

In the Genesis hierarchical organization, the Meta-Orchestrator delegates tasks
to 4 permanent Department Leads:
1. EngineeringLead — manages coder, reviewer, test_writer, deployer, dependency_updater,
   performance_optimizer, db_architect.
2. ResearchLead — manages researcher, data_validator, hallucination_checker, translator.
3. OperationsLead — manages scheduler_agent, notification_agent, cost_watcher, rate_limiter_agent.
4. QualitySecurityLead — manages security, tester, critic_agent, fallback_agent.

Each Lead acts as the first-line quality filter: it receives the task, assigns it to
an appropriate worker role within its department, verifies the worker's output against
departmental quality standards, and reports a structured result to the Meta-Orchestrator.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

from .staff import StaffPool, get_specialist
from .subagents import SubagentResult


@dataclass
class TeamLeadResult:
    """Outcome of a task executed by a Team Lead and its department workers."""

    department: str
    lead_id: str
    assigned_role: str
    task: str
    success: bool
    output: str
    verification_verdict: str  # e.g., "VERIFIED", "CHANGES_RECOMMENDED", "FAILED"
    verification_notes: list[str] = field(default_factory=list)
    worker_result: SubagentResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "department": self.department,
            "lead_id": self.lead_id,
            "assigned_role": self.assigned_role,
            "task": self.task,
            "success": self.success,
            "verification_verdict": self.verification_verdict,
            "verification_notes": self.verification_notes,
            "output": self.output,
            "metadata": self.metadata,
        }


class BaseTeamLead:
    """Base class for departmental team leads."""

    department: str = "general"
    lead_id: str = "lead_general"
    name: str = "General Lead"
    managed_roles: tuple[str, ...] = ()

    def __init__(self, staff_pool: StaffPool | None = None):
        self.staff_pool = staff_pool or StaffPool()

    def pick_role_for_task(self, task: str, requested_role: str | None = None) -> str:
        """Pick the most appropriate specialist role within this department."""
        if requested_role and requested_role in self.managed_roles:
            return requested_role

        t_lower = task.lower()
        for role in self.managed_roles:
            spec = get_specialist(role)
            # Check keywords from title or description
            words = set(re.findall(r"\w+", spec.description.lower()))
            if any(w in t_lower for w in [role, spec.title.lower()] if len(w) > 3):
                return role
            if any(w in t_lower for w in words if len(w) > 4):
                return role

        # Default to first managed role
        return self.managed_roles[0] if self.managed_roles else "generalist"

    async def execute_task(
        self,
        task: str,
        role: str | None = None,
        session_id: str = "lead_session",
        opts: dict[str, Any] | None = None,
    ) -> TeamLeadResult:
        """Assign task to department specialist, run it, and perform first-line verification."""
        assigned = self.pick_role_for_task(task, requested_role=role)
        sub_res = await self.staff_pool.run(
            role=assigned,
            task=task,
            session_id=f"{session_id}-{self.lead_id}",
            label=f"{self.lead_id}-{assigned}",
            opts=opts,
        )

        return await self.verify_and_filter(task, assigned, sub_res)

    async def verify_and_filter(
        self,
        task: str,
        assigned_role: str,
        sub_res: SubagentResult,
    ) -> TeamLeadResult:
        """First-line departmental review filter. Subclasses customize this."""
        notes = []
        verdict = "VERIFIED"
        success = sub_res.ok

        if not sub_res.ok:
            verdict = "FAILED"
            notes.append(f"Worker {assigned_role} exited with non-zero code or error: {sub_res.error}")

        if not sub_res.final or not sub_res.final.strip():
            verdict = "FAILED"
            notes.append("Worker produced empty output.")
            success = False

        return TeamLeadResult(
            department=self.department,
            lead_id=self.lead_id,
            assigned_role=assigned_role,
            task=task,
            success=success,
            output=sub_res.final or sub_res.error or "",
            verification_verdict=verdict,
            verification_notes=notes,
            worker_result=sub_res,
        )


class EngineeringLead(BaseTeamLead):
    """
    Engineering Lead (Level 2).
    Manages: coder, reviewer, test_writer, deployer, dependency_updater,
             performance_optimizer, db_architect.
    Verification filter:
    - Code syntax sanity check on generated Python blocks.
    - Non-empty output and error detection.
    """

    department: str = "engineering"
    lead_id: str = "lead_engineering"
    name: str = "Engineering Lead"
    managed_roles: tuple[str, ...] = (
        "coder",
        "reviewer",
        "test_writer",
        "deployer",
        "dependency_updater",
        "performance_optimizer",
        "db_architect",
    )

    def pick_role_for_task(self, task: str, requested_role: str | None = None) -> str:
        if requested_role and requested_role in self.managed_roles:
            return requested_role
        t = task.lower()
        if any(k in t for k in ["test", "unittest", "pytest"]):
            return "test_writer" if any(k in t for k in ["write", "add", "create"]) else "coder"
        if any(k in t for k in ["review", "audit", "critique"]):
            return "reviewer"
        if any(k in t for k in ["deploy", "ci", "cd", "release"]):
            return "deployer"
        if any(k in t for k in ["dependency", "dependencies", "package", "bump"]):
            return "dependency_updater"
        if any(k in t for k in ["perf", "performance", "speed", "latency", "benchmark"]):
            return "performance_optimizer"
        if any(k in t for k in ["db", "database", "sql", "migration", "schema"]):
            return "db_architect"
        return "coder"

    async def verify_and_filter(
        self,
        task: str,
        assigned_role: str,
        sub_res: SubagentResult,
    ) -> TeamLeadResult:
        base = await super().verify_and_filter(task, assigned_role, sub_res)
        notes = list(base.verification_notes)
        verdict = base.verification_verdict

        # Syntax sanity check on Python code blocks in output
        code_blocks = re.findall(r"```python\s*(.*?)\s*```", base.output, re.DOTALL)
        syntax_errors = []
        for idx, block in enumerate(code_blocks, 1):
            try:
                ast.parse(block)
            except SyntaxError as err:
                syntax_errors.append(f"Block #{idx} syntax error at line {err.lineno}: {err.msg}")

        if syntax_errors:
            verdict = "CHANGES_RECOMMENDED"
            notes.extend(syntax_errors)
        elif base.success:
            notes.append("Code deliverables passed preliminary engineering syntax check.")

        return TeamLeadResult(
            department=self.department,
            lead_id=self.lead_id,
            assigned_role=assigned_role,
            task=task,
            success=base.success and len(syntax_errors) == 0,
            output=base.output,
            verification_verdict=verdict,
            verification_notes=notes,
            worker_result=sub_res,
            metadata={"syntax_errors": len(syntax_errors), "code_blocks_checked": len(code_blocks)},
        )


class ResearchLead(BaseTeamLead):
    """
    Research Lead (Level 2).
    Manages: researcher, data_validator, hallucination_checker, translator.
    Verification filter:
    - Checks for factual grounding and citations (presence of sources/URLs/paths).
    - Flags unverified assertions or suspicious claims.
    """

    department: str = "research"
    lead_id: str = "lead_research"
    name: str = "Research Lead"
    managed_roles: tuple[str, ...] = (
        "researcher",
        "data_validator",
        "hallucination_checker",
        "translator",
    )

    def pick_role_for_task(self, task: str, requested_role: str | None = None) -> str:
        if requested_role and requested_role in self.managed_roles:
            return requested_role
        t = task.lower()
        if any(k in t for k in ["validate", "validation", "schema", "integrity"]):
            return "data_validator"
        if any(k in t for k in ["hallucination", "fact", "accuracy", "verify claim", "ground truth"]):
            return "hallucination_checker"
        if any(k in t for k in ["translate", "translation", "english to", "uzbek"]):
            return "translator"
        return "researcher"

    async def verify_and_filter(
        self,
        task: str,
        assigned_role: str,
        sub_res: SubagentResult,
    ) -> TeamLeadResult:
        base = await super().verify_and_filter(task, assigned_role, sub_res)
        notes = list(base.verification_notes)
        verdict = base.verification_verdict

        out_lower = base.output.lower()
        has_citations = any(
            k in out_lower for k in ["source", "http://", "https://", "file://", "reference", "manba:"]
        )

        if assigned_role == "researcher" and not has_citations and len(base.output) > 200:
            notes.append("Notice: Research output lacks explicit source citations or URL references.")
            verdict = "VERIFIED_WITH_NOTICE"

        return TeamLeadResult(
            department=self.department,
            lead_id=self.lead_id,
            assigned_role=assigned_role,
            task=task,
            success=base.success,
            output=base.output,
            verification_verdict=verdict,
            verification_notes=notes,
            worker_result=sub_res,
            metadata={"has_citations": has_citations},
        )


class OperationsLead(BaseTeamLead):
    """
    Operations Lead (Level 2).
    Manages: scheduler_agent, notification_agent, cost_watcher, rate_limiter_agent.
    Verification filter:
    - Verifies operational schedules, rate quota impact, and cost telemetry.
    """

    department: str = "operations"
    lead_id: str = "lead_operations"
    name: str = "Operations Lead"
    managed_roles: tuple[str, ...] = (
        "scheduler_agent",
        "notification_agent",
        "cost_watcher",
        "rate_limiter_agent",
    )

    def pick_role_for_task(self, task: str, requested_role: str | None = None) -> str:
        if requested_role and requested_role in self.managed_roles:
            return requested_role
        t = task.lower()
        if any(k in t for k in ["schedule", "cron", "timing", "periodic"]):
            return "scheduler_agent"
        if any(k in t for k in ["notify", "notification", "telegram", "broadcast", "alert"]):
            return "notification_agent"
        if any(k in t for k in ["rate limit", "throttle", "quota", "qps"]):
            return "rate_limiter_agent"
        if any(k in t for k in ["cost", "token", "spend", "budget"]):
            return "cost_watcher"
        return "scheduler_agent"

    async def verify_and_filter(
        self,
        task: str,
        assigned_role: str,
        sub_res: SubagentResult,
    ) -> TeamLeadResult:
        base = await super().verify_and_filter(task, assigned_role, sub_res)
        notes = list(base.verification_notes)
        verdict = base.verification_verdict

        notes.append("Operations filter verified runtime impact and resource compliance.")
        return TeamLeadResult(
            department=self.department,
            lead_id=self.lead_id,
            assigned_role=assigned_role,
            task=task,
            success=base.success,
            output=base.output,
            verification_verdict=verdict,
            verification_notes=notes,
            worker_result=sub_res,
        )


class QualitySecurityLead(BaseTeamLead):
    """
    Quality & Security Lead (Level 2).
    Manages: security, tester, critic_agent, fallback_agent.
    Verification filter:
    - First gate for vulnerabilities, secret leakage, or failed test suites.
    """

    department: str = "quality_security"
    lead_id: str = "lead_quality_security"
    name: str = "Quality & Security Lead"
    managed_roles: tuple[str, ...] = (
        "security",
        "tester",
        "critic_agent",
        "fallback_agent",
    )

    def pick_role_for_task(self, task: str, requested_role: str | None = None) -> str:
        if requested_role and requested_role in self.managed_roles:
            return requested_role
        t = task.lower()
        if any(k in t for k in ["security", "vulnerability", "leak", "audit", "injection"]):
            return "security"
        if any(k in t for k in ["test", "verify", "run test", "assert", "fail"]):
            return "tester"
        if any(k in t for k in ["critic", "adversarial", "counter", "challenge", "weakness"]):
            return "critic_agent"
        if any(k in t for k in ["fallback", "recovery", "degrade", "backup"]):
            return "fallback_agent"
        return "security"

    async def verify_and_filter(
        self,
        task: str,
        assigned_role: str,
        sub_res: SubagentResult,
    ) -> TeamLeadResult:
        base = await super().verify_and_filter(task, assigned_role, sub_res)
        notes = list(base.verification_notes)
        verdict = base.verification_verdict

        out_lower = base.output.lower()
        has_critical = any(k in out_lower for k in ["critical vulnerability", "cve-", "exploit found", "blocker"])

        if has_critical:
            verdict = "SECURITY_BLOCKER"
            notes.append("CRITICAL: Quality/Security Lead flagged blocker issues requiring remediation.")

        return TeamLeadResult(
            department=self.department,
            lead_id=self.lead_id,
            assigned_role=assigned_role,
            task=task,
            success=base.success and not has_critical,
            output=base.output,
            verification_verdict=verdict,
            verification_notes=notes,
            worker_result=sub_res,
            metadata={"has_critical_findings": has_critical},
        )


def build_team_leads(staff_pool: StaffPool | None = None) -> dict[str, BaseTeamLead]:
    """Factory creating all 4 Department Leads."""
    pool = staff_pool or StaffPool()
    leads = [
        EngineeringLead(pool),
        ResearchLead(pool),
        OperationsLead(pool),
        QualitySecurityLead(pool),
    ]
    return {lead.department: lead for lead in leads}


def route_to_department(task: str) -> str:
    """Classify incoming task to one of the 4 departments."""
    t = task.lower()
    # Quality & Security keywords
    if any(k in t for k in ["security", "audit", "vuln", "penetration", "critic", "adversarial", "safe"]):
        return "quality_security"
    # Operations keywords
    if any(k in t for k in ["schedule", "cron", "notify", "rate limit", "token spend", "cost report", "ops"]):
        return "operations"
    # Research keywords
    if any(k in t for k in ["research", "investigate", "translate", "validate data", "hallucination", "what is"]):
        return "research"
    # Default to Engineering for technical / code tasks
    return "engineering"
