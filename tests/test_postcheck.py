"""Phase 26 tests: bounded auto post-check for edit runs.

When a run actually WROTE or EDITED files, one extra bounded model iteration is
injected before finalizing: re-read the changed files, run the relevant
verification, and only then ship the final answer. Read-only runs and
runs with the feature disabled are byte-for-byte unchanged. The pass is
bounded to exactly one per run. Deterministic fake LLM + fake executor.
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


def _tool_call(name="write_file", args='{"path": "p.txt", "content": "x"}'):
    return {"id": None, "function": {"name": name, "arguments": args}}


class _FakeExec:
    def __init__(self):
        self.executed: list[tuple] = []

    async def __call__(self, name, args):
        self.executed.append((name, args))
        if name == "write_file":
            return "written"
        return "EVIDENCE"


async def _run(llm, tmp_path, session="p", fake_exec=None):
    agent = TitanAgent(
        llm=llm,
        memory=MemoryManager(tmp_path / "p.db"),
        core_memory_path=tmp_path / "p_core.db",
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
    return (finals[0] if finals else None), events, statuses


def test_edit_run_gets_one_postcheck_pass(tmp_path):
    """A run that wrote a file gets exactly ONE extra verification turn; the
    model is explicitly told to verify before finalizing."""
    fake = _FakeExec()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),   # call 1: write
        LLMResponse(content="DRAFT"),                         # call 2: draft
        LLMResponse(content="CRIT"),                          # call 3: critic
        LLMResponse(content="VERIFIED-FINAL"),                # call 4: post-check
    ])
    final, _events, statuses = asyncio.run(_run(llm, tmp_path, fake_exec=fake, session="p1"))
    assert final == "VERIFIED-FINAL"
    assert llm.calls == 4
    assert sum("Post-check" in s for s in statuses) == 1
    assert any("You just edited files" in s for s in llm.seen_system)


def test_readonly_run_skips_postcheck(tmp_path):
    """No write/edit tools -> no post-check, classic behavior unchanged."""
    fake = _FakeExec()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[
            _tool_call(name="read_file", args='{"path": "x"}')
        ]),
        LLMResponse(content="DRAFT"),
        LLMResponse(content="CRIT"),
    ])
    final, _events, statuses = asyncio.run(_run(llm, tmp_path, fake_exec=fake, session="p2"))
    assert final == "CRIT"
    assert llm.calls == 3
    assert not any("Post-check" in s for s in statuses)


def test_postcheck_disabled_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_AUTO_POSTCHECK", "0")
    fake = _FakeExec()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="DRAFT"),
        LLMResponse(content="CRIT"),
    ])
    final, _events, statuses = asyncio.run(_run(llm, tmp_path, fake_exec=fake, session="p3"))
    assert final == "CRIT"
    assert llm.calls == 3
    assert not any("Post-check" in s for s in statuses)


def test_postcheck_round_may_use_tools(tmp_path):
    """The post-check round can itself verify with tools (e.g. re-reading the
    file); the loop stays bounded and then finalizes."""
    fake = _FakeExec()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),   # call 1: write
        LLMResponse(content="DRAFT"),                         # call 2: draft
        LLMResponse(content="CRIT"),                          # call 3: critic
        LLMResponse(content="", tool_calls=[
            _tool_call(name="read_file", args='{"path": "p.txt"}')
        ]),                                                  # call 4: verify
        LLMResponse(content="VERIFIED-FINAL"),               # call 5: final
    ])
    final, _events, statuses = asyncio.run(_run(llm, tmp_path, fake_exec=fake, session="p4"))
    assert final == "VERIFIED-FINAL"
    assert llm.calls == 5
    assert any(name == "read_file" for name, _ in fake.executed)
    assert sum("Post-check" in s for s in statuses) == 1