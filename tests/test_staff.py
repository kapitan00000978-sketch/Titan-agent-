"""Phase 9 — Dedicated Subagent Staff: deterministic tests (no LLM/network).

Covers the roster, role resolution/aliases, ToolPolicy filtering + enforcement,
agent-level catalog filtering, execute_tool_unified role blocking, StaffPool
run/team semantics with an injected runner, and the staff catalog surface.
"""
import asyncio

from titan_agent.agent import TitanAgent
from titan_agent.staff import (
    SPECIALISTS,
    Specialist,
    StaffPool,
    ToolPolicy,
    get_specialist,
    staff_catalog,
)

VALID_MODES = ("fast", "deep", "deep_search")
VALID_EFFORTS = ("auto", "low", "medium", "high", "ultra")
VALID_STRATEGIES = ("auto", "plan", "react", "tot")


# --------------------------------------------------------------------------
# Roster integrity
# --------------------------------------------------------------------------

def test_roster_unique_ids_and_generalist():
    ids = list(SPECIALISTS)
    assert len(ids) == len(set(ids))
    assert "generalist" in ids
    for rid, id_ in enumerate(ids):
        spec = SPECIALISTS[id_]
        assert spec.id == id_


def test_roster_fields_valid():
    for spec in SPECIALISTS.values():
        assert spec.mode in VALID_MODES, spec.id
        assert spec.effort in VALID_EFFORTS, spec.id
        assert spec.strategy in VALID_STRATEGIES, spec.id
        assert spec.title and spec.description


def test_generalist_has_no_persona_and_full_tools():
    g = SPECIALISTS["generalist"]
    assert g.persona == ""
    assert g.allowed_tools is None
    assert g.blocked_tools == frozenset()


def test_specialists_have_personas_and_policies():
    for rid in ("planner", "researcher", "coder", "reviewer", "tester"):
        spec = SPECIALISTS[rid]
        assert spec.persona.strip(), rid
        assert spec.description, rid
    assert SPECIALISTS["researcher"].mode == "deep_search"
    assert "git_commit" in SPECIALISTS["researcher"].blocked_tools
    assert SPECIALISTS["reviewer"].allowed_tools is not None
    assert "git_commit" not in SPECIALISTS["reviewer"].allowed_tools  # allowlist blocks commit
    assert "write_file" not in SPECIALISTS["reviewer"].allowed_tools


def test_phase11_specialists_have_personas_and_policies():
    """Phase 11 roster: every new role has a persona + sane tool boundaries."""
    for rid in (
        "security", "test_writer", "summarizer", "memory_keeper", "cost_watcher",
        "triager", "doc_writer", "changelogger", "deployer", "dependency_updater",
        "router",
    ):
        spec = SPECIALISTS[rid]
        assert spec.persona.strip(), rid
        assert spec.description, rid
    assert "git_commit" in SPECIALISTS["security"].blocked_tools
    assert "write_file" in SPECIALISTS["security"].blocked_tools
    # Writers-of-docs/tests: may write to disk, but never commit.
    for rid in ("test_writer", "doc_writer", "changelogger"):
        assert "write_file" not in SPECIALISTS[rid].blocked_tools
        assert "git_commit" in SPECIALISTS[rid].blocked_tools
    # Read-only roles carry an allowlist.
    for rid in ("summarizer", "memory_keeper", "cost_watcher"):
        assert SPECIALISTS[rid].allowed_tools is not None
    # The router must plan, not mutate.
    assert "write_file" in SPECIALISTS["router"].blocked_tools
    assert "git_commit" in SPECIALISTS["router"].blocked_tools


# --------------------------------------------------------------------------
# Role resolution + aliases
# --------------------------------------------------------------------------

def test_get_specialist_resolves_unknown_to_generalist():
    assert get_specialist(None).id == "generalist"
    assert get_specialist("").id == "generalist"
    assert get_specialist("no-such-role").id == "generalist"
    assert get_specialist("CODEr").id == "coder"  # case-insensitive


def test_get_specialist_aliases():
    assert get_specialist("code").id == "coder"
    assert get_specialist("developer").id == "coder"
    assert get_specialist("research").id == "researcher"
    assert get_specialist("plan").id == "planner"
    assert get_specialist("critic").id == "reviewer"
    assert get_specialist("qa").id == "tester"


# --------------------------------------------------------------------------
# ToolPolicy
# --------------------------------------------------------------------------

def test_tool_policy_blocked():
    p = ToolPolicy(blocked=frozenset({"git_commit", "write_file"}))
    assert p.allows("read_file")
    assert not p.allows("git_commit")
    assert not p.allows("write_file")


def test_tool_policy_allowed_only():
    p = ToolPolicy(allowed=frozenset({"read_file", "rag_search"}))
    assert p.allows("read_file")
    assert not p.allows("write_file")
    assert not p.allows("execute_command")


def test_tool_policy_all_simple():
    p = ToolPolicy()
    assert p.allows("anything")


def test_tool_policy_filter_definitions():
    defs = [
        {"type": "function", "function": {"name": "write_file", "description": "x"}},
        {"type": "function", "function": {"name": "read_file", "description": "y"}},
    ]
    p = ToolPolicy(blocked=frozenset({"write_file"}))
    out = p.filter_definitions(defs)
    assert [d["function"]["name"] for d in out] == ["read_file"]
    assert ToolPolicy().filter_definitions(defs) == defs


# --------------------------------------------------------------------------
# Agent-level policy: catalog filter + execution enforcement
# --------------------------------------------------------------------------

class _FakeTools:
    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "read_file", "description": "reads"}},
            {"type": "function", "function": {"name": "write_file", "description": "writes"}},
            {"type": "function", "function": {"name": "execute_command", "description": "runs"}},
        ]

    async def execute_tool(self, name, args):
        return f"executed:{name}"


class _FakeMCP:
    def get_all_tools(self):
        return []


def _role_agent(policy: ToolPolicy | None) -> TitanAgent:
    return TitanAgent(
        llm=None,
        tools=_FakeTools(),
        mcp=_FakeMCP(),
        memory=None,
        skills=None,
        telegram=None,
        tool_policy=policy,
    )


def test_agent_catalog_filters_blocked_tools():
    agent = _role_agent(ToolPolicy(blocked=frozenset({"write_file", "execute_command"})))
    catalog = agent._build_tool_catalog_text()
    assert "read_file" in catalog
    assert "write_file" not in catalog
    assert "execute_command" not in catalog


def test_agent_catalog_unfiltered_without_policy():
    agent = _role_agent(None)
    catalog = agent._build_tool_catalog_text()
    assert "read_file" in catalog
    assert "write_file" in catalog
    assert "execute_command" in catalog


def test_execute_tool_unified_blocks_role_tool():
    agent = _role_agent(ToolPolicy(blocked=frozenset({"write_file"})))
    res = asyncio.run(agent.execute_tool_unified("write_file", {"path": "x"}))
    assert "outside this subagent's role" in res
    assert "write_file" in res


def test_execute_tool_unified_allows_role_tool():
    agent = _role_agent(ToolPolicy(blocked=frozenset({"write_file"})))
    res = asyncio.run(agent.execute_tool_unified("read_file", {"path": "x.txt"}))
    assert res == "executed:read_file"


def test_execute_tool_unified_no_policy_allows_everything():
    agent = _role_agent(None)
    res = asyncio.run(agent.execute_tool_unified("write_file", {"path": "x"}))
    assert res == "executed:write_file"


def test_build_tools_list_filters():
    agent = _role_agent(ToolPolicy(allowed=frozenset({"read_file"})))
    names = [t["function"]["name"] for t in agent._build_tools_list()]
    assert names == ["read_file"]


# --------------------------------------------------------------------------
# StaffPool with injected runner
# --------------------------------------------------------------------------

def _make_pool(calls: list[tuple[str, str, dict]]):
    def fake_run(spec: Specialist, task: str, opts: dict) -> tuple[int, str, list]:
        calls.append((spec.id, task, opts))
        return 0, f"answer from {spec.id}: {task}", []

    return StaffPool(runner=fake_run, max_workers=2)


def test_staff_run_picks_specialist_and_session():
    calls = []
    pool = _make_pool(calls)
    res = asyncio.run(pool.run("coder", "implement login", session_id="parent-1"))
    assert res.exit_code == 0
    assert res.final == "answer from coder: implement login"
    assert res.error is None
    spec_id, task, opts = calls[0]
    assert spec_id == "coder"
    assert task == "implement login"
    assert opts["session_id"].startswith("sub-parent-1-")
    assert "coder" in opts["session_id"]


def test_staff_run_alias_and_label():
    calls = []
    pool = _make_pool(calls)
    asyncio.run(pool.run("research", "who are we?", label="r1", session_id="s"))
    assert calls[0][0] == "researcher"
    assert "r1" in calls[0][2]["session_id"]


def test_staff_run_error_is_reported():
    def boom(spec, task, opts):
        raise RuntimeError("child crash")

    pool = StaffPool(runner=boom)
    res = asyncio.run(pool.run("coder", "x"))
    assert res.exit_code == 1
    assert res.error == "child crash"
    assert "ERROR" in res.to_text()


def test_staff_team_respects_roles_and_order():
    calls = []
    pool = _make_pool(calls)
    results = asyncio.run(pool.team(
        ["plan A", "review B", "write C"],
        roles=["planner", "reviewer", "coder"],
        session_id="s",
    ))
    assert [r.final for r in results] == [
        "answer from planner: plan A",
        "answer from reviewer: review B",
        "answer from coder: write C",
    ]
    assert [c[0] for c in calls] == ["planner", "reviewer", "coder"]


def test_staff_team_defaults_to_generalist():
    calls = []
    pool = _make_pool(calls)
    results = asyncio.run(pool.team(["a", "b"], roles=["coder"], session_id="s"))
    assert len(results) == 2
    assert [c[0] for c in calls] == ["coder", "generalist"]


def test_staff_team_empty():
    pool = _make_pool([])
    assert asyncio.run(pool.team([], session_id="s")) == []


# --------------------------------------------------------------------------
# Catalog surface for the parent agent
# --------------------------------------------------------------------------

def test_staff_catalog_lists_non_generalist_roles():
    catalog = staff_catalog()
    ids = {e["id"] for e in catalog}
    assert ids == {
        "planner", "researcher", "coder", "reviewer", "tester",
        # Phase 11 roster: quality, safety, memory, monitoring, docs, ops, router
        "security", "test_writer", "summarizer", "memory_keeper", "cost_watcher",
        "triager", "doc_writer", "changelogger", "deployer", "dependency_updater",
        "router",
    }
    for e in catalog:
        assert e["title"] and e["description"]


def test_tool_subagent_roles_returns_catalog():
    from titan_agent.tools import ToolRegistry

    out = ToolRegistry().tool_subagent_roles()
    assert "DEDICATED SUBAGENT ROLES" in out
    for rid in ("planner", "researcher", "coder", "reviewer", "tester",
                "security", "test_writer", "summarizer", "memory_keeper",
                "cost_watcher", "triager", "doc_writer", "changelogger",
                "deployer", "dependency_updater", "router"):
        assert f"- {rid}: " in out


def test_agent_prompt_mentions_staff_tools():
    from titan_agent.agent import TITAN_SYSTEM_PROMPT

    for name in ("subagent_roles", "subagent_route", "planner", "researcher",
                 "coder", "reviewer", "tester", "security", "test_writer",
                 "summarizer", "memory_keeper", "cost_watcher", "triager",
                 "doc_writer", "changelogger", "deployer", "dependency_updater",
                 "router"):
        assert name in TITAN_SYSTEM_PROMPT


def test_tool_catalog_definitions_have_new_params():
    from titan_agent.tools import ToolRegistry

    defs = ToolRegistry().get_tool_definitions()
    by_name = {}
    for d in defs:
        fn = d.get("function", {})
        by_name[fn.get("name")] = fn.get("parameters", {}).get("properties", {})
    assert "role" in by_name["subagent_delegate"]
    assert "roles" in by_name["subagent_team"]
    assert "subagent_roles" in by_name