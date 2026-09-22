"""Phase 37 tests: dead-end early stop.

When EVERY tool call in a batch fails (error return, malformed skip, or guard
block) there is no evidence of progress. After TITAN_DEAD_END_WINDOW (default 5)
consecutive all-failed tool batches the harness stops early with an explicit
notice instead of burning the remaining steps/tokens; ANY successful tool result
resets the streak; 0 disables the detector entirely. Deterministic: scripted
fake LLM + fake tool executor, no network.
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


def _tool_call(url="http://example.test/a"):
    return {
        "id": None,
        "function": {"name": "web_fetch", "arguments": f'{{"url": "{url}"}}'},
    }


class _AlwaysFail:
    """Every call fails; identical args are enough for the repeat guard too."""

    def __init__(self):
        self.executed = 0

    async def __call__(self, name, args):
        self.executed += 1
        return "Error: connection timeout"


class _ScriptedExec:
    """Fails until a URL is in the fail set, then succeeds for others."""

    def __init__(self, fail_urls):
        self.fail_urls = set(fail_urls)
        self.executed = []

    async def __call__(self, name, args):
        url = str(args.get("url", ""))
        self.executed.append(url)
        if url in self.fail_urls:
            return "Error: connection timeout"
        return f"OK fetched {url}"


async def _run(llm, tmp_path, fake_exec=None, session="d"):
    agent = TitanAgent(
        llm=llm,
        memory=MemoryManager(tmp_path / "d.db"),
        core_memory_path=tmp_path / "d_core.db",
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
    return (finals[0] if finals else None), statuses, agent


def test_dead_end_stops_after_window(tmp_path):
    # Five all-failed batches (default window) stop the run before a sixth
    # LLM call happens - the model never gets to grind on.
    fake = _AlwaysFail()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="FINAL"),
    ])
    final, statuses, _ = asyncio.run(_run(llm, tmp_path, fake_exec=fake, session="d1"))
    assert final is not None and "Stopped early" in final
    assert llm.calls == 5          # the 6th call (FINAL) was never requested
    assert any("Dead end detected" in s for s in statuses)


def test_dead_end_window_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_DEAD_END_WINDOW", "3")
    fake = _AlwaysFail()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="FINAL"),
    ])
    final, _, _ = asyncio.run(_run(llm, tmp_path, fake_exec=fake, session="d2"))
    assert final is not None and "Stopped early" in final
    assert llm.calls == 3


def test_success_resets_streak(tmp_path, monkeypatch):
    """A successful tool result resets the dead-end streak, so a run that
    recovers survives instead of being cut off."""
    monkeypatch.setenv("TITAN_DEAD_END_WINDOW", "2")
    fake = _ScriptedExec(fail_urls=["http://example.test/b"])
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),              # fail
        LLMResponse(content="", tool_calls=[_tool_call()]),              # fail (streak 2)
        LLMResponse(content="", tool_calls=[_tool_call("http://example.test/c")]),  # success -> reset
        LLMResponse(content="", tool_calls=[_tool_call()]),              # fail (streak 1)
        LLMResponse(content="FINAL"),
        LLMResponse(content="CRIT"),                                     # reflection
    ])
    final, _, _ = asyncio.run(_run(llm, tmp_path, fake_exec=fake, session="d3"))
    assert final == "CRIT"
    assert "Stopped early" not in (final or "")


def test_dead_end_disabled_runs_to_completion(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_DEAD_END_WINDOW", "0")
    fake = _AlwaysFail()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="FINAL"),
        LLMResponse(content="CRIT"),
    ])
    final, _, _ = asyncio.run(_run(llm, tmp_path, fake_exec=fake, session="d4"))
    assert final == "CRIT"


def test_dead_end_streak_exposed_on_agent(tmp_path):
    """The per-run streak is observable on the agent (fed to /api/guard/state)."""
    fake = _AlwaysFail()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="FINAL"),
        LLMResponse(content="FINAL"),
    ])
    _, _, agent = asyncio.run(_run(llm, tmp_path, fake_exec=fake, session="d5"))
    assert agent._consecutive_failed_batches == 2