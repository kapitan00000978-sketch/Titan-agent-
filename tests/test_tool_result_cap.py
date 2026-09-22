"""Phase 34 tests: tool-result size cap.

A single oversized tool output (a log dump, a whole-file read) can flood the
model's context window. Tool results appended to the conversation are capped
at TITAN_TOOL_RESULT_MAX_CHARS with an explicit truncation marker that keeps
the true total length, so the model knows output was cut and how large it
actually was. Nothing under the cap changes. Deterministic: fake executor that
returns a deliberately oversized payload, no network.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.agent import TitanAgent
from titan_agent.llm_client import LLMResponse
from titan_agent.memory import MemoryManager


class _RecordingLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.all_tool_contents: list[str] = []

    async def chat_completion(self, messages, tools=None, **kw):
        self.calls += 1
        self.all_tool_contents.extend(
            str(m["content"])
            for m in messages
            if m.get("role") == "tool"
        )
        if not self.responses:
            return LLMResponse(content="done")
        return self.responses.pop(0)


def _tool_call(name="web_fetch", args='{"url": "http://example.test/big"}'):
    return {"id": None, "function": {"name": name, "arguments": args}}


class _BigOutputExec:
    def __init__(self, chars: int = 500):
        self.chars = chars

    async def __call__(self, name, args):
        return "x" * self.chars


async def _run(llm, tmp_path, session="c", fake_exec=None):
    agent = TitanAgent(
        llm=llm,
        memory=MemoryManager(tmp_path / "c.db"),
        core_memory_path=tmp_path / "c_core.db",
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
    return (finals[0] if finals else None), tool_results


def test_cap_result_short_unchanged(tmp_path):
    agent = TitanAgent(
        llm=_RecordingLLM([]),
        memory=MemoryManager(tmp_path / "c1.db"),
        core_memory_path=tmp_path / "c1_core.db",
    )
    assert agent._cap_tool_result("short") == "short"
    assert agent._cap_tool_result("") == ""


def test_cap_result_oversized_marker(tmp_path):
    """Oversized output keeps its head plus a marker naming the true total."""
    agent = TitanAgent(
        llm=_RecordingLLM([]),
        memory=MemoryManager(tmp_path / "c2.db"),
        core_memory_path=tmp_path / "c2_core.db",
    )
    out = agent._cap_tool_result("a" * 9000)
    assert "[tool output truncated: 9000 chars total" in out
    assert out.startswith("a" * 4000)


def test_cap_result_env_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_TOOL_RESULT_MAX_CHARS", "120")
    agent = TitanAgent(
        llm=_RecordingLLM([]),
        memory=MemoryManager(tmp_path / "c3.db"),
        core_memory_path=tmp_path / "c3_core.db",
    )
    out = agent._cap_tool_result("b" * 300)
    assert "[tool output truncated: 300 chars total" in out
    assert out.startswith("b" * 120)


def test_oversized_tool_result_capped_in_run(tmp_path, monkeypatch):
    """End-to-end: a tool returning a huge payload reaches the model's
    conversation truncated, with the marker; the run finalizes normally."""
    monkeypatch.setenv("TITAN_TOOL_RESULT_MAX_CHARS", "300")
    fake = _BigOutputExec(chars=500)
    llm = _RecordingLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),   # 1: tool use
        LLMResponse(content="FINAL"),                          # 2: draft
        LLMResponse(content="CRIT"),                           # 3: critic
    ])
    final, tool_results = asyncio.run(
        _run(llm, tmp_path, session="c4", fake_exec=fake)
    )
    assert final == "CRIT"
    assert llm.calls == 3
    assert len(tool_results) == 1
    assert "[tool output truncated: 500 chars total" in tool_results[0]
    assert len(tool_results[0].splitlines()[0]) == 300
    # the appended tool message heard by the model is the SAME capped text
    assert any(
        "[tool output truncated: 500 chars total" in c for c in llm.all_tool_contents
    )