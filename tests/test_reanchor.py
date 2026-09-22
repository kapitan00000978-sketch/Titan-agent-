"""Phase 24 tests: task re-anchoring after context compaction.

Long runs lose the ORIGINAL objective when old messages get compacted, worst
with small models. When compaction actually drops messages — either in the
proactive per-iteration trim inside run_task or during provider-window
overflow halving in _chat_with_recovery — a compact system reminder re-pins
the original task right before the next model call. Only fires after
compaction, so short runs are byte-for-byte unchanged.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.agent import (
    ORIGINAL_TASK_MARKER,
    ORIGINAL_TASK_MAX_CHARS,
    TitanAgent,
    _anchor_block,
)
from titan_agent.llm_client import LLMResponse
from titan_agent.memory import MemoryManager


class _RecordingLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.seen_systems = []  # system-message contents per chat_completion call

    async def chat_completion(self, messages, tools=None, **kw):
        self.calls += 1
        self.seen_systems.append(
            [str(m.get("content") or "") for m in messages if m.get("role") == "system"]
        )
        # The context summarizer calls us with a single-user-message prompt; it
        # must NOT consume a scripted main-loop response (compaction eats a
        # queue entry per trimmed round, which would starve the run).
        if (len(messages) == 1 and messages[0].get("role") == "user"
                and "compacting" in str(messages[0].get("content") or "")):
            return LLMResponse(content="SUMMARY of earlier dropped context.")
        if not self.responses:
            return LLMResponse(content="done")
        return self.responses.pop(0)


class _BigExec:
    def __init__(self):
        self.executed = 0

    async def __call__(self, name, args):
        self.executed += 1
        return "OK " + ("x" * 290)  # ~300 chars per result to blow the window


def _tool_call(name="run_command", args='{"command": "echo x"}'):
    return {"id": None, "function": {"name": name, "arguments": args}}


def _has_anchor(systems) -> bool:
    return any(
        ORIGINAL_TASK_MARKER in content
        for content_list in systems
        for content in content_list
    )


def _run(tmp_path, llm, session, fake_exec=None, budget=None):
    """Run a full task with optional budget override. Patches are applied only
    for the duration of the run (restored even if the run fails)."""
    with pytest.MonkeyPatch.context() as mp:
        if budget:
            mp.setattr("titan_agent.agent.CONTEXT_BUDGET_CHARS", budget)
            mp.setenv("TITAN_FINAL_GROUNDING", "0")
        agent = TitanAgent(
            llm=llm,
            memory=MemoryManager(tmp_path / "r.db"),
            core_memory_path=tmp_path / "r_core.db",
        )
        if fake_exec is not None:
            agent.execute_tool_unified = fake_exec
        events = []
        finals = []
        async def _collect():
            nonlocal events, finals
            async for ev in agent.run_task(
                "REFACTOR THE AUTH MODULE AND KEEP ALL TESTS GREEN",
                session_id=session, mode="fast", strategy="auto",
            ):
                events.append(ev)
                if ev.type == "final_answer":
                    finals.append(ev.data)
            return finals[0] if finals else None

        result = asyncio.run(_collect())
    return result, events, llm


# ---------------------------------------------------------------------------
# In-run proactive compaction triggers the anchor
# ---------------------------------------------------------------------------


def test_in_run_compaction_reanchors_task(tmp_path):
    llm = _RecordingLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="FINAL"),
        LLMResponse(content="FINAL"),  # reflection pass
    ])
    final, events, llm = _run(
        tmp_path, llm, session="ra1", fake_exec=_BigExec(), budget=900
    )
    assert final == "FINAL"
    assert llm.calls >= 5
    assert _has_anchor(llm.seen_systems)
    # the original objective text is pinned, not mangled
    assert any(
        "REFACTOR THE AUTH MODULE" in content
        for content_list in llm.seen_systems
        for content in content_list
    )
    assert any(
        ev.type == "status" and "Re-anchored" in str(ev.data) for ev in events
    )


def test_no_compaction_never_anchors(tmp_path):
    llm = _RecordingLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="FINAL"),
        LLMResponse(content="FINAL"),
    ])
    final, events, llm = _run(
        tmp_path, llm, session="ra2", fake_exec=_BigExec()
    )
    assert final == "FINAL"
    assert not _has_anchor(llm.seen_systems)
    assert not any(
        ev.type == "status" and "Re-anchored" in str(ev.data) for ev in events
    )


def test_reanchor_disabled_via_env(tmp_path):
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("titan_agent.agent.CONTEXT_BUDGET_CHARS", 900)
        mp.setenv("TITAN_TASK_REANCHOR", "0")
        mp.setenv("TITAN_FINAL_GROUNDING", "0")
        llm = _RecordingLLM([
            LLMResponse(content="", tool_calls=[_tool_call()]),
            LLMResponse(content="", tool_calls=[_tool_call()]),
            LLMResponse(content="", tool_calls=[_tool_call()]),
            LLMResponse(content="FINAL"),
            LLMResponse(content="FINAL"),
        ])
        final, _events, llm = _run(
            tmp_path, llm, session="ra3", fake_exec=_BigExec()
        )
    assert final == "FINAL"
    assert not _has_anchor(llm.seen_systems)
    assert not any(
        ev.type == "status" and "Re-anchored" in str(ev.data) for ev in _events
    )


# ---------------------------------------------------------------------------
# Overflow halving inside _chat_with_recovery also re-anchors
# ---------------------------------------------------------------------------


class _OverflowOnceLLM:
    def __init__(self):
        self.calls = 0

    async def chat_completion(self, messages, tools=None, **kw):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("context length exceeded by 5000 tokens")
        return LLMResponse(content="done")


def test_overflow_halving_reanchors(tmp_path):
    llm = _OverflowOnceLLM()
    agent = TitanAgent(
        llm=llm,
        memory=MemoryManager(tmp_path / "h.db"),
        core_memory_path=tmp_path / "h_core.db",
    )
    big = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "original user objective"},
    ]
    for k in range(15):
        big.append({"role": "assistant", "content": "",
                    "tool_calls": [{"id": f"c{k}",
                                    "function": {"name": "run_command",
                                                 "arguments": "{}"}}]})
        big.append({"role": "tool", "tool_call_id": f"c{k}",
                    "name": "run_command", "content": "y" * 300})

    resp, working, notes = asyncio.run(
        agent._chat_with_recovery(big, [], anchor="overflow anchor task")
    )
    assert resp.content == "done"
    assert any("Context overflow" in n for n in notes)
    contents = [str(m.get("content") or "") for m in working]
    assert any(ORIGINAL_TASK_MARKER in c for c in contents)
    assert any("overflow anchor task" in c for c in contents)


# ---------------------------------------------------------------------------
# _anchor_block + no-duplicate guarantee
# ---------------------------------------------------------------------------


def test_anchor_block_content_and_truncation():
    assert _anchor_block("") is None
    assert _anchor_block("   ") is None
    b = _anchor_block("do the thing")
    assert b["role"] == "system"
    assert "do the thing" in b["content"]
    long_task = "z" * (ORIGINAL_TASK_MAX_CHARS * 2)
    b2 = _anchor_block(long_task)
    assert "…" in b2["content"]
    assert len(b2["content"]) < ORIGINAL_TASK_MAX_CHARS * 2


def test_reanchor_task_appends_once(tmp_path):
    agent = TitanAgent(
        llm=_RecordingLLM([LLMResponse(content="done")]),
        memory=MemoryManager(tmp_path / "d.db"),
        core_memory_path=tmp_path / "d_core.db",
    )
    msgs = [{"role": "system", "content": "SYS"},
            {"role": "user", "content": "task"}]
    agent._reanchor_task(msgs, "anchored objective")
    assert sum(
        ORIGINAL_TASK_MARKER in str(m.get("content") or "") for m in msgs
    ) == 1
    count_after_first = sum(
        ORIGINAL_TASK_MARKER in str(m.get("content") or "") for m in msgs
    )
    agent._reanchor_task(msgs, "anchored objective")
    assert sum(
        ORIGINAL_TASK_MARKER in str(m.get("content") or "") for m in msgs
    ) == count_after_first
    # nothing to anchor -> no-op
    msgs2 = [{"role": "system", "content": "SYS"}]
    agent._reanchor_task(msgs2, "  ")
    assert len(msgs2) == 1