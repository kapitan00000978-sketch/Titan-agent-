"""Phase 23 tests: repeated tool-failure guard.

Weak models re-send the SAME failing tool call with the SAME arguments over
and over. The harness tracks identical (tool, canonical-args) patterns that
already failed in this run and, after TITAN_REPEAT_GUARD_LIMIT identical
failures, SKIPS further identical attempts with an explanatory error so the
model changes approach. Tests are deterministic: scripted fake LLM + fake
tool executor that fails on demand, no network, guard counters reset per run.
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


def _tool_call(name="web_fetch", args='{"url": "http://example.test/a"}'):
    return {"id": None, "function": {"name": name, "arguments": args}}


class _FailingExec:
    """Every identical call fails with the same error string."""

    def __init__(self):
        self.executed = 0

    async def __call__(self, name, args):
        self.executed += 1
        return "Error: connection timeout"


class _SucceedingExec:
    def __init__(self):
        self.executed = 0

    async def __call__(self, name, args):
        self.executed += 1
        return f"OK {args.get('url', '')}"


async def _run(llm, tmp_path, fake_exec=None, session="g"):
    agent = TitanAgent(
        llm=llm,
        memory=MemoryManager(tmp_path / "g.db"),
        core_memory_path=tmp_path / "g_core.db",
    )
    if fake_exec is not None:
        agent.execute_tool_unified = fake_exec
    events, finals = await _run_on_agent(agent, session)
    return (finals[0] if finals else None), events, agent


async def _run_on_agent(agent, session):
    events = []
    finals = []
    async for ev in agent.run_task(
        "task", session_id=session, mode="fast", strategy="auto"
    ):
        events.append(ev)
        if ev.type == "final_answer":
            finals.append(ev.data)
    return events, finals


def _tool_results(events):
    return [ev.data["result"] for ev in events if ev.type == "tool_result"]


def test_identical_failure_blocked_after_limit(tmp_path):
    fake_exec = _FailingExec()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="FINAL"),
        LLMResponse(content="FINAL"),  # reflection pass
    ])
    final, events, _ = asyncio.run(_run(llm, tmp_path, fake_exec=fake_exec, session="g1"))
    assert final == "FINAL"
    assert fake_exec.executed == 2          # two real attempts
    results = _tool_results(events)
    assert len(results) == 3
    assert results[0].startswith("Error: connection timeout")
    assert results[1].startswith("Error: connection timeout")
    assert "repeated tool failure guard" in results[2]
    assert llm.calls == 5


def test_different_args_have_own_counters(tmp_path):
    fake_exec = _FailingExec()
    args_b = '{"url": "http://example.test/b"}'
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),                # A fail -> A=1
        LLMResponse(content="", tool_calls=[_tool_call(args=args_b)]),     # B fail -> B=1
        LLMResponse(content="", tool_calls=[_tool_call()]),                # A fail -> A=2
        LLMResponse(content="", tool_calls=[_tool_call()]),                # A blocked
        LLMResponse(content="FINAL"),
        LLMResponse(content="FINAL"),
    ])
    final, events, _ = asyncio.run(_run(llm, tmp_path, fake_exec=fake_exec, session="g2"))
    assert final == "FINAL"
    assert fake_exec.executed == 3                       # A, B, A — not the blocked A
    results = _tool_results(events)
    assert "repeated tool failure guard" == results[3][:28] or \
        "repeated tool failure guard" in results[3]


def test_success_forgives_pattern(tmp_path):
    fake_exec = _SucceedingExec()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="FINAL"),
        LLMResponse(content="FINAL"),
    ])
    final, events, _ = asyncio.run(_run(llm, tmp_path, fake_exec=fake_exec, session="g3"))
    assert final == "FINAL"
    assert fake_exec.executed == 3                       # never blocked
    assert not any("repeated tool failure guard" in r for r in _tool_results(events))


def test_limit_one_blocks_second_attempt(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_REPEAT_GUARD_LIMIT", "1")
    fake_exec = _FailingExec()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="FINAL"),
        LLMResponse(content="FINAL"),
    ])
    final, events, _ = asyncio.run(_run(llm, tmp_path, fake_exec=fake_exec, session="g4"))
    assert final == "FINAL"
    assert fake_exec.executed == 1
    assert "repeated tool failure guard" in _tool_results(events)[1]


def test_guard_disabled_runs_every_call(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_REPEAT_GUARD", "0")
    fake_exec = _FailingExec()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="FINAL"),
        LLMResponse(content="FINAL"),
    ])
    final, events, _ = asyncio.run(_run(llm, tmp_path, fake_exec=fake_exec, session="g5"))
    assert final == "FINAL"
    assert fake_exec.executed == 3
    assert not any("repeated tool failure guard" in r for r in _tool_results(events))


def test_guard_state_resets_each_run(tmp_path):
    fake_exec = _FailingExec()
    llm1 = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="FINAL"),
        LLMResponse(content="FINAL"),
    ])
    f1, _events1, agent = asyncio.run(_run(llm1, tmp_path, fake_exec=fake_exec, session="g6a"))
    assert f1 == "FINAL"
    assert fake_exec.executed == 1

    # Second run on the SAME agent instance: the guard state must be fresh,
    # so the identical call executes again instead of being blocked.
    llm2 = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="FINAL"),
        LLMResponse(content="FINAL"),
    ])
    agent.llm = llm2
    events2, finals2 = asyncio.run(_run_on_agent(agent, "g6b"))
    assert finals2 == ["FINAL"]
    assert fake_exec.executed == 2                       # ran again -> state reset
    results2 = _tool_results(events2)
    assert results2[0].startswith("Error: connection timeout")
    assert "repeated tool failure guard" not in results2[0]