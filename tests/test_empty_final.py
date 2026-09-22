"""Phase 30 tests: empty final-answer guard.

Weak models occasionally end a run with whitespace-only content — the run
"succeeds" while telling the user nothing. The harness retries ONCE with a
bounded system prompt; if the model still returns nothing, the final answer is
an explicit notice instead of a silent empty success. Deterministic fake LLM.
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
        self.seen_system: list[str] = []

    async def chat_completion(self, messages, tools=None, **kw):
        self.calls += 1
        self.seen_system.extend(
            str(m["content"]) for m in messages if m.get("role") == "system"
        )
        if not self.responses:
            return LLMResponse(content="done")
        return self.responses.pop(0)


def _tool_call(name="memory_save", args='{"key": "k", "value": "v"}'):
    return {"id": None, "function": {"name": name, "arguments": args}}


class _FakeExec:
    async def __call__(self, name, args):
        return "EVIDENCE"


async def _run(llm, tmp_path, session="q", fake_exec=None):
    agent = TitanAgent(
        llm=llm,
        memory=MemoryManager(tmp_path / "q.db"),
        core_memory_path=tmp_path / "q_core.db",
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
    statuses = [str(ev.data) for ev in events if ev.type == "status"]
    return (finals[0] if finals else None), statuses


def test_empty_final_gets_one_bounded_retry(tmp_path):
    """Whitespace-only content triggers ONE bounded retry with a system prompt
    telling the model to actually answer, then the run finalizes normally."""
    llm = _QueuedLLM([
        LLMResponse(content=""),          # call 1: empty -> retry
        LLMResponse(content="REAL-ANSWER"),    # call 2: candidate final
        LLMResponse(content="GROUNDED-FINAL"),  # call 3: grounding pass
    ])
    final, statuses = asyncio.run(_run(llm, tmp_path, session="q1"))
    assert final == "GROUNDED-FINAL"
    assert llm.calls == 3
    assert any("Empty response" in s for s in statuses)
    assert any("Produce the FINAL answer" in s for s in llm.seen_system)


def test_second_empty_becomes_explicit_notice(tmp_path):
    """If the retry is ALSO empty, the run ends with an explicit notice — never
    a silent empty success."""
    llm = _QueuedLLM([
        LLMResponse(content=""),   # call 1: empty -> retry
        LLMResponse(content=""),   # call 2: still empty -> notice
    ])
    final, statuses = asyncio.run(_run(llm, tmp_path, session="q2"))
    assert final.startswith("⚠ The model produced an empty final answer")
    assert llm.calls == 2
    assert any("Empty response" in s for s in statuses)


def test_guard_disabled_immediate_notice(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_EMPTY_FINAL_GUARD", "0")
    llm = _QueuedLLM([LLMResponse(content="")])
    final, statuses = asyncio.run(_run(llm, tmp_path, session="q3"))
    assert final.startswith("⚠ The model produced an empty final answer")
    assert llm.calls == 1
    assert not any("Empty response" in s for s in statuses)


def test_empty_final_after_tool_use_retries_once(tmp_path):
    """A tool-using run that then answers empty still gets exactly one retry
    (bounded — no infinite loop) and the reflection pass still runs."""
    fake = _FakeExec()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),  # call 1: tool use
        LLMResponse(content=""),                             # call 2: empty -> retry
        LLMResponse(content="REAL-ANSWER"),                  # call 3: candidate
        LLMResponse(content="CRIT"),                         # call 4: reflection
    ])
    final, statuses = asyncio.run(_run(llm, tmp_path, fake_exec=fake, session="q4"))
    assert final == "CRIT"
    assert llm.calls == 4
    assert sum("Empty response" in s for s in statuses) == 1