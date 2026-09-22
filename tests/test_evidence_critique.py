"""Phase 25 tests: evidence-aware critique.

The critic/reflection prompt receives a deterministic "TOOL EVIDENCE" block
built from the REAL tool round-trips already in the conversation (tool names,
results, files written/edited), so a weak critic argues against facts instead
of vibes. No extra LLM call — only the prompt content changes. Deterministic
fake LLM + fake executor, no network.
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
    """Scripted responses; records every call's user messages for assertion."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.user_contents: list[list[str]] = []

    async def chat_completion(self, messages, tools=None, **kw):
        self.calls += 1
        self.user_contents.append(
            [str(m["content"]) for m in messages if m.get("role") == "user"]
        )
        if not self.responses:
            return LLMResponse(content="done")
        return self.responses.pop(0)


def _tool_call(name="read_file", args='{"path": "x"}'):
    return {"id": "call_e", "function": {"name": name, "arguments": args}}


class _FakeExec:
    def __init__(self):
        self.executed: list[tuple] = []

    async def __call__(self, name, args):
        self.executed.append((name, args))
        return "EVIDENCE"


async def _run(llm, tmp_path, session="e", fake_exec=None):
    agent = TitanAgent(
        llm=llm,
        memory=MemoryManager(tmp_path / "e.db"),
        core_memory_path=tmp_path / "e_core.db",
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
    return (finals[0] if finals else None), events, agent


def _critic_user_contents(llm):
    """The last user message of each call whose prompt is the reflection."""
    out = []
    for contents in llm.user_contents:
        if contents and contents[-1].startswith("You are the CRITIC phase"):
            out.append(contents[-1])
    return out


def test_critique_receives_tool_evidence(tmp_path):
    """After a tool-using run the critic prompt lists what actually happened:
    tool names + result snippets. No write tools -> no file list."""
    fake = _FakeExec()
    llm = _RecordingLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),   # call 1: tool use
        LLMResponse(content="DRAFT"),                         # call 2: draft
        LLMResponse(content="CRITICAL-FINAL"),                # call 3: critic
    ])
    final, _events, _ = asyncio.run(_run(llm, tmp_path, fake_exec=fake, session="e1"))
    assert final == "CRITICAL-FINAL"
    assert llm.calls == 3

    critics = _critic_user_contents(llm)
    assert len(critics) == 1
    prompt = critics[0]
    assert "#### TOOL EVIDENCE" in prompt
    assert "read_file: EVIDENCE" in prompt
    assert "Files written/edited" not in prompt  # no write tools ran


def test_evidence_lists_written_files(tmp_path):
    """The evidence block extracts the real file paths written/edited and
    includes them so the critic can verify against disk facts."""
    agent = TitanAgent(
        llm=_RecordingLLM([]),
        memory=MemoryManager(tmp_path / "e2.db"),
        core_memory_path=tmp_path / "e2_core.db",
    )
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "notes/a.txt", "content": "hi"}',
                    },
                }
            ],
        },
        {"role": "tool", "name": "write_file", "tool_call_id": "c1", "content": "written"},
    ]
    block = agent._build_tool_evidence(messages)
    assert "#### TOOL EVIDENCE" in block
    assert "notes/a.txt" in block
    assert "- write_file: written" in block


def test_evidence_deduplicates_paths(tmp_path):
    """Same file written twice appears once in the files list."""
    agent = TitanAgent(
        llm=_RecordingLLM([]),
        memory=MemoryManager(tmp_path / "e3.db"),
        core_memory_path=tmp_path / "e3_core.db",
    )
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "a.txt", "content": "1"}',
                    },
                },
                {
                    "id": "c2",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "a.txt", "content": "2"}',
                    },
                },
            ],
        }
    ]
    block = agent._build_tool_evidence(messages)
    files_line = [ln for ln in block.splitlines() if "Files written/edited" in ln]
    assert len(files_line) == 1
    assert files_line[0].count("a.txt") == 1