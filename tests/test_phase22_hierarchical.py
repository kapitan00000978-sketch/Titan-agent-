"""
Tests for Phase 22 Genesis Level Hierarchical Architecture:
- 27 Specialists Roster & Aliases
- 4 Department Leads & Verification Filters
- Meta-Orchestrator, GlobalGoalMemory, ResourceBudget, ConflictResolver
- Hierarchical Tool Integration (orchestrator_run, team_delegate, team_status)
"""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from titan_agent.orchestrator import (
    ConflictResolver,
    GlobalGoalMemory,
    MetaOrchestrator,
    ResourceBudget,
)
from titan_agent.staff import SPECIALISTS, get_specialist, staff_catalog
from titan_agent.subagents import SubagentResult
from titan_agent.team_leads import (
    EngineeringLead,
    QualitySecurityLead,
    TeamLeadResult,
    build_team_leads,
    route_to_department,
)
from titan_agent.tools import ToolRegistry


def test_specialists_genesis_roster():
    """Verify all specialists exist and are properly configured."""
    assert len(SPECIALISTS) == 29
    catalog = staff_catalog()
    assert len(catalog) == 28  # generalist excluded from specialized catalog

    new_roles = [
        "data_validator",
        "hallucination_checker",
        "translator",
        "scheduler_agent",
        "notification_agent",
        "rate_limiter_agent",
        "critic_agent",
        "fallback_agent",
        "performance_optimizer",
        "db_architect",
    ]
    for role in new_roles:
        spec = get_specialist(role)
        assert spec.id == role
        assert spec.title
        assert spec.persona

    # Test alias resolution
    assert get_specialist("fact_check").id == "hallucination_checker"
    assert get_specialist("translate").id == "translator"
    assert get_specialist("perf").id == "performance_optimizer"
    assert get_specialist("db").id == "db_architect"
    assert get_specialist("adversarial").id == "critic_agent"


def test_department_routing_and_roles():
    """Verify task classification into departments and lead role assignment."""
    leads = build_team_leads()
    assert set(leads.keys()) == {"engineering", "research", "operations", "quality_security"}

    # Department classification
    assert route_to_department("Fix memory leak in web server") == "engineering"
    assert route_to_department("Translate API documentation into Uzbek") == "research"
    assert route_to_department("Schedule periodic cron backup every midnight") == "operations"
    assert route_to_department("Audit codebase for SQL injection and security leaks") == "quality_security"

    # Lead role pickers
    eng = leads["engineering"]
    assert eng.pick_role_for_task("Write unit test for auth module") == "test_writer"
    assert eng.pick_role_for_task("Optimize query latency") == "performance_optimizer"
    assert eng.pick_role_for_task("Create Postgres migration") == "db_architect"

    res = leads["research"]
    assert res.pick_role_for_task("Validate user JSON schema") == "data_validator"
    assert res.pick_role_for_task("Check fact accuracy against sources") == "hallucination_checker"

    ops = leads["operations"]
    assert ops.pick_role_for_task("Send telegram broadcast alert") == "notification_agent"
    assert ops.pick_role_for_task("Check API rate limits and throttling") == "rate_limiter_agent"

    sec = leads["quality_security"]
    assert sec.pick_role_for_task("Perform adversarial critique of architecture") == "critic_agent"
    assert sec.pick_role_for_task("Run security vulnerability scan") == "security"


@pytest.mark.asyncio
async def test_engineering_lead_verification_filter():
    """Engineering lead catches syntax errors in generated code blocks."""
    lead = EngineeringLead()

    # Case 1: valid code
    valid_sub = SubagentResult(
        label="test",
        exit_code=0,
        final="Here is the fix:\n```python\ndef hello():\n    return 'world'\n```",
    )
    res_valid = await lead.verify_and_filter("implement hello", "coder", valid_sub)
    assert res_valid.success is True
    assert res_valid.verification_verdict == "VERIFIED"

    # Case 2: invalid syntax
    invalid_sub = SubagentResult(
        label="test",
        exit_code=0,
        final="Broken code:\n```python\ndef hello(\n    return 'broken'\n```",
    )
    res_invalid = await lead.verify_and_filter("implement hello", "coder", invalid_sub)
    assert res_invalid.success is False
    assert res_invalid.verification_verdict == "CHANGES_RECOMMENDED"
    assert any("syntax error" in note.lower() for note in res_invalid.verification_notes)


@pytest.mark.asyncio
async def test_quality_security_lead_verification_filter():
    """Quality & Security lead flags critical blockers."""
    lead = QualitySecurityLead()

    # Blocker finding
    blocker_sub = SubagentResult(
        label="test",
        exit_code=0,
        final="Audit complete. CRITICAL VULNERABILITY found: SQL injection at line 42.",
    )
    res = await lead.verify_and_filter("audit database", "security", blocker_sub)
    assert res.success is False
    assert res.verification_verdict == "SECURITY_BLOCKER"
    assert any("blocker" in note.lower() for note in res.verification_notes)


def test_global_goal_memory(tmp_path: Path):
    """Test persistence and tracking in GlobalGoalMemory."""
    mem_file = tmp_path / "goals.json"
    mem = GlobalGoalMemory(storage_path=mem_file)

    mem.set_project_goal("Build autonomous self-healing agent")
    m1 = mem.add_milestone("m1", "Deploy v1.0", department="engineering")
    assert m1.status == "pending"

    mem.complete_milestone("m1", notes="Deployed successfully")
    assert mem.milestones[0].status == "completed"

    # Reload from file
    mem2 = GlobalGoalMemory(storage_path=mem_file)
    assert mem2.project_goal == "Build autonomous self-healing agent"
    assert len(mem2.milestones) == 1
    assert mem2.milestones[0].status == "completed"


def test_resource_budget():
    """Test ResourceBudget consumption and limits."""
    budget = ResourceBudget(max_tokens=1000, max_steps=10)
    assert not budget.is_exhausted()

    budget.record_usage("engineering", tokens=400, steps=3)
    budget.record_usage("research", tokens=300, steps=2)
    assert budget.total_tokens() == 700
    assert budget.total_steps() == 5
    assert not budget.is_exhausted()

    budget.record_usage("operations", tokens=400, steps=1)
    assert budget.is_exhausted()


def test_conflict_resolver():
    """Test multi-department arbitration."""
    resolver = ConflictResolver()

    # Case 1: All clean
    r1 = TeamLeadResult(
        department="engineering",
        lead_id="lead_eng",
        assigned_role="coder",
        task="code",
        success=True,
        output="Code ready",
        verification_verdict="VERIFIED",
    )
    verdict, rationale = resolver.arbitrate([r1])
    assert verdict == "APPROVED"

    # Case 2: Security blocker overrides engineering success
    r_sec = TeamLeadResult(
        department="quality_security",
        lead_id="lead_sec",
        assigned_role="security",
        task="audit",
        success=False,
        output="Critical leak",
        verification_verdict="SECURITY_BLOCKER",
    )
    verdict, rationale = resolver.arbitrate([r1, r_sec])
    assert verdict == "REMEDIATE"
    assert "Security overrides engineering" in rationale


@pytest.mark.asyncio
async def test_meta_orchestrator_orchestration():
    """Test end-to-end orchestration lifecycle with mocked leads."""
    mock_eng_lead = MagicMock()
    mock_eng_lead.department = "engineering"
    mock_eng_lead.lead_id = "lead_engineering"
    mock_eng_lead.name = "Engineering Lead"
    mock_eng_lead.managed_roles = ("coder",)

    mock_res = TeamLeadResult(
        department="engineering",
        lead_id="lead_engineering",
        assigned_role="coder",
        task="Build new component",
        success=True,
        output="Component successfully implemented.",
        verification_verdict="VERIFIED",
        verification_notes=["Syntax clean"],
    )
    mock_eng_lead.execute_task = AsyncMock(return_value=mock_res)

    leads = {"engineering": mock_eng_lead}
    orch = MetaOrchestrator(leads=leads)

    res = await orch.orchestrate("Build new component", departments=["engineering"])
    assert res.success is True
    assert res.final_verdict == "APPROVED"
    assert "TITAN META-ORCHESTRATOR EXECUTIVE REPORT" in res.synthesis
    assert "Component successfully implemented." in res.synthesis
    assert orch.budget.total_tokens() > 0


def test_hierarchical_tool_status():
    """Test ToolRegistry team_status output."""
    tools = ToolRegistry()
    status = tools.tool_team_status()
    assert "TITAN HIERARCHICAL ORGANIZATION STATUS" in status
    assert "Engineering Lead" in status
    assert "Research Lead" in status
    assert "Operations Lead" in status
    assert "Quality & Security Lead" in status
