"""Phase 33 tests: repeated malformed-arguments guard.

Tool calls whose arguments cannot be parsed as valid JSON are SKIPPED — they
must never run with empty arguments. But a weak model re-sends THE SAME broken
call over and over; skipped calls never reach `execute_tool_unified`, so the
Phase 27 repeated-failure guard cannot see them. Phase 33 counts skipped
malformed calls per tool NAME and, past `TITAN_MALFORMED_GUARD_LIMIT`, blocks
further malformed calls from that tool with actionable guidance. Counters reset
per run. Deterministic: fake LLM emitting malformed tool calls, never executes.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.agent import TitanAgent
from titan_agent.llm_client import LLMResponse
from titan_agent.memory import MemoryManager


class _QueuedLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def chat_completion(self, messages, tools=None, **kw):
        self.calls += 1
        if not self.responses:
            return LLMResponse(content="done")
        return self.responses.pop(0)


def _malformed_call(name="web_fetch"):
    return {
        "id": None,
        "function": {"name": name, "arguments": '{"url": unquoted}'},
    }


class _CountingExec:
    def __init__(self):
        self.executed = 0

    async def __call__(self, name, args):
        self.executed += 1
        return "EVIDENCE"


async def _run(llm, tmp_path, session="m", fake_exec=None):
    agent = TitanAgent(
        llm=llm,
        memory=MemoryManager(tmp_path / "m.db"),
        core_memory_path=tmp_path / "m_core.db",
    )
    if fake_exec is not None:
        agent._execute_tool_unified = fake_exec
    events = [
        ev
        async for ev in agent.run_task(
            "task", session_id=session, mode="fast", strategy="auto"
        )
    ]
    finals = [ev.data for ev in events if ev.type == "final_answer"]
    tool_results = [
        str(ev.data.get("result", ""))
        for ev in events
        if ev.type == "tool_result"
    ]
    statuses = [str(ev.data) for ev in events if ev.type == "status"]
    return (finals[0] if finals else None), tool_results, statuses, agent


def test_malformed_calls_blocked_after_limit(tmp_path):
    """Same malformed tool call sent 3 times: first is a plain skip, the 2nd
    and 3rd are BLOCKED with the guard message; the tool never executes and
    the run still finishes normally (reflection included)."""
    fake = _CountingExec()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_malformed_call()]),  # 1: skip
        LLMResponse(content="", tool_calls=[_malformed_call()]),  # 2: blocked
        LLMResponse(content="", tool_calls=[_malformed_call()]),  # 3: blocked
        LLMResponse(content="FINAL"),                             # 4: draft
        LLMResponse(content="CRIT"),                              # 5: critic
    ])
    final, tool_results, statuses, _ = asyncio.run(
        _run(llm, tmp_path, session="m1", fake_exec=fake)
    )
    assert final == "CRIT"
    assert llm.calls == 5
    assert fake.executed == 0                       # never executed a malformed call
    assert tool_results[0].startswith("Skipped: tool arguments")
    assert "repeated malformed-arguments guard" in tool_results[1]
    assert "repeated malformed-arguments guard" in tool_results[2]
    assert "Blocking malformed 'web_fetch'" in " | ".join(statuses)


def test_malformed_guard_disabled(tmp_path, monkeypatch):
    """Disabled: every malformed call is a plain skip — no guard message."""
    monkeypatch.setenv("TITAN_MALFORMED_GUARD", "0")
    fake = _CountingExec()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_malformed_call()]),
        LLMResponse(content="", tool_calls=[_malformed_call()]),
        LLMResponse(content="FINAL"),
        LLMResponse(content="CRIT"),
    ])
    final, tool_results, statuses, _ = asyncio.run(
        _run(llm, tmp_path, session="m2", fake_exec=fake)
    )
    assert final == "CRIT"
    assert fake.executed == 0
    assert all(r.startswith("Skipped: tool arguments") for r in tool_results)
    assert not any("repeated malformed-arguments guard" in r for r in tool_results)
    assert not any("Blocking malformed" in s for s in statuses)


def test_malformed_limit_from_env(tmp_path, monkeypatch):
    """A higher TITAN_MALFORMED_GUARD_LIMIT tolerates more skips before blocking."""
    monkeypatch.setenv("TITAN_MALFORMED_GUARD_LIMIT", "3")
    fake = _CountingExec()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_malformed_call()]),  # 1: skip
        LLMResponse(content="", tool_calls=[_malformed_call()]),  # 2: skip
        LLMResponse(content="", tool_calls=[_malformed_call()]),  # 3: skip
        LLMResponse(content="", tool_calls=[_malformed_call()]),  # 4: blocked
        LLMResponse(content="FINAL"),
        LLMResponse(content="CRIT"),
    ])
    final, tool_results, _, _ = asyncio.run(
        _run(llm, tmp_path, session="m3", fake_exec=fake)
    )
    assert final == "CRIT"
    assert fake.executed == 0
    assert tool_results[0].startswith("Skipped: tool arguments")
    assert tool_results[1].startswith("Skipped: tool arguments")
    assert "repeated malformed-arguments guard" in tool_results[2]
    assert "repeated malformed-arguments guard" in tool_results[3]


def test_malformed_counters_reset_per_run(tmp_path):
    """The guard state is per-run: the second run starts counting from zero
    and blocks fresh at the limit again (no stale memory of run 1)."""
    agent_holder: dict[str, TitanAgent] = {}

    async def run_once(agent):
        events = [
            ev
            async for ev in agent.run_task(
                "task", session_id="m4", mode="fast", strategy="auto"
            )
        ]
        return [ev.data for ev in events if ev.type == "final_answer"]

    async def scenario():
        fake1 = _CountingExec()
        llm1 = _QueuedLLM([
            LLMResponse(content="", tool_calls=[_malformed_call()]),
            LLMResponse(content="", tool_calls=[_malformed_call()]),
            LLMResponse(content="FINAL"),
            LLMResponse(content="CRIT"),
        ])
        agent = TitanAgent(
            llm=llm1,
            memory=MemoryManager(tmp_path / "m4.db"),
            core_memory_path=tmp_path / "m4_core.db",
        )
        agent._execute_tool_unified = fake1
        agent_holder["agent"] = agent
        f1 = await run_once(agent)
        assert f1 == ["CRIT"]
        assert fake1.executed == 0
        assert agent._malformed_calls["web_fetch"] == 2

        # Second run: state must be fresh; identical malformed pattern is again
        # skipped once, then blocked.
        fake2 = _CountingExec()
        llm2 = _QueuedLLM([
            LLMResponse(content="", tool_calls=[_malformed_call()]),
            LLMResponse(content="", tool_calls=[_malformed_call()]),
            LLMResponse(content="", tool_calls=[_malformed_call()]),
            LLMResponse(content="FINAL"),
            LLMResponse(content="CRIT"),
        ])
        agent.llm = llm2
        agent._execute_tool_unified = fake2
        f2 = await run_once(agent)
        assert f2 == ["CRIT"]
        assert agent._malformed_calls["web_fetch"] == 3

    asyncio.run(scenario())