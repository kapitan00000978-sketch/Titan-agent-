"""Phase 36 tests: delegated-subagent failures flow through the failure funnel.

Delegation is a TOOL like any other. When the delegated child FAILS or ERRORS,
the result must read as a failed tool EXECUTION (Error-prefixed) so the uniform
funnel records it — per-tool telemetry, the repeated-failure guard (re-delegating
the identical task eventually gets blocked) and the critic's TOOL EVIDENCE all
see the failure. A weak parent must never treat a crashing child's half-baked
output as proven work. Deterministic: patched StaffPool + a live ToolRegistry
and its real tool path, no network.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import titan_agent.staff as staff_mod
from titan_agent.subagents import SubagentResult
from titan_agent.tools import ToolRegistry


class _FailingPool:
    """As StaffPool, but every run returns a FAILED child."""

    def __init__(self, exit_code: int = 1, final: str = "half-baked output",
                 error: str | None = None, **kwargs):
        self.exit_code = exit_code
        self.final = final
        self.error = error

    async def run(self, role, task, label="", **kwargs):
        return SimpleNamespace(
            label=label or role,
            exit_code=self.exit_code,
            final=self.final,
            error=self.error,
            events=[],
        )

    async def team(self, tasks, roles=None, **kwargs):
        return [
            SimpleNamespace(
                label=f"worker-{i + 1}",
                exit_code=self.exit_code,
                final=self.final,
                error=self.error,
                events=[],
            )
            for i in range(len(tasks))
        ]


def test_failed_delegate_reads_as_tool_error(monkeypatch):
    monkeypatch.setattr(staff_mod, "StaffPool", _FailingPool)
    out = asyncio.run(
        ToolRegistry().tool_subagent_delegate(
            "implement the parser", role="coder", label="c1"
        )
    )
    assert out.startswith("Error: ")
    assert "FAILED (exit 1)" in out
    assert "half-baked output" in out
    # The parent is explicitly told not to present the failure as done work.
    assert "UNPROVEN" in out


def test_errored_delegate_is_explicit_error(monkeypatch):
    monkeypatch.setattr(staff_mod, "StaffPool", _FailingPool)
    out = asyncio.run(
        ToolRegistry().tool_subagent_delegate(
            "query the database", role="researcher", label="r1"
        )
    )
    assert out.startswith("Error: ")
    assert "FAILED (exit 1)" in out
    assert "UNPROVEN" in out


def test_crashed_delegate_reports_its_error(monkeypatch):
    """A child that raised (error set) is reported as an ERROR with its message,
    still Error-prefixed so the funnel records it as a failed execution."""

    class _CrashedPool(_FailingPool):
        def __init__(self, **kwargs):
            super().__init__(error="child crash", **kwargs)

    monkeypatch.setattr(staff_mod, "StaffPool", _CrashedPool)
    out = asyncio.run(
        ToolRegistry().tool_subagent_delegate(
            "query the database", role="researcher", label="r1"
        )
    )
    assert out.startswith("Error: ")
    assert "ERROR" in out
    assert "child crash" in out
    assert "UNPROVEN" in out


def test_success_output_unchanged(monkeypatch):
    class _OkPool:
        async def run(self, role, task, label="", **kwargs):
            return SubagentResult(
                label=label or "worker", exit_code=0, final="all good here"
            )

    monkeypatch.setattr(staff_mod, "StaffPool", _OkPool)
    out = asyncio.run(
        ToolRegistry().tool_subagent_delegate("a task", role="coder", label="c1")
    )
    assert out.startswith("### SUBAGENT [c1]")
    assert "all good here" in out
    assert not out.startswith("Error:")
    assert "UNPROVEN" not in out


def test_team_failures_marked_individually(monkeypatch):
    monkeypatch.setattr(staff_mod, "StaffPool", _FailingPool)
    out = asyncio.run(
        ToolRegistry().tool_subagent_team(
            ["plan the work", "review it"], roles=["planner", "reviewer"]
        )
    )
    assert out.startswith("Error: ")
    assert out.count("### SUBAGENT") == 2
    assert "UNPROVEN" in out


def test_repeat_delegation_blocked_via_funnel(tmp_path, monkeypatch):
    """The failed delegation feeds the repeated-failure guard: the THIRD
    identical delegation of the same task is blocked before the pool runs."""
    from titan_agent.agent import TitanAgent
    from titan_agent.memory import MemoryManager

    class _StubLLM:
        async def chat_completion(self, messages, tools=None, **kw):
            return LLMResponse(content="idle")

    from titan_agent.llm_client import LLMResponse

    monkeypatch.setattr(staff_mod, "StaffPool", _FailingPool)
    agent = TitanAgent(
        llm=_StubLLM(),
        memory=MemoryManager(tmp_path / "d.db"),
        core_memory_path=tmp_path / "d_core.db",
    )
    args = {"task": "make the module", "role": "coder", "label": "w"}
    r1 = asyncio.run(agent.execute_tool_unified("subagent_delegate", args))
    r2 = asyncio.run(agent.execute_tool_unified("subagent_delegate", args))
    r3 = asyncio.run(agent.execute_tool_unified("subagent_delegate", args))
    assert r1.startswith("Error: ")
    assert r2.startswith("Error: ")
    # The guard records actual block decisions for observability too.
    assert "repeated tool failure guard" in r3
    assert agent._guard_totals.get("blocked_repeat", 0) >= 1