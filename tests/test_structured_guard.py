"""Phase 32 tests: repeated-failure guard works through the structured funnel.

Structured engines (react / plan / tot) never touched the classic loop, so the
Phase 23 guard originally only protected the classic path. Phase 27 moved the
guard INTO execute_tool_unified — and Phase 27/32 prove the structured path
gets it too: a ToolBridge wired to the LIVE wrapper is blocked on the third
identical failing call. Deterministic fake executor, no network.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.agent import TitanAgent
from titan_agent.llm_client import LLMResponse
from titan_agent.memory import MemoryManager
from titan_agent.structured import ToolBridge


class _SilentLLM:
    async def chat_completion(self, messages, tools=None, **kw):
        return LLMResponse(content="done")


class _FailingExec:
    def __init__(self):
        self.executed = 0

    async def __call__(self, name, args):
        self.executed += 1
        return "Error: connection timeout"


def test_guard_blocks_third_call_via_tool_bridge(tmp_path):
    """A ToolBridge (the exact adapter structured engines execute through) is
    wired to the live wrapper — the third identical failing call is blocked."""
    agent = TitanAgent(
        llm=_SilentLLM(),
        memory=MemoryManager(tmp_path / "s.db"),
        core_memory_path=tmp_path / "s_core.db",
    )
    agent._execute_tool_unified = _FailingExec()
    bridge = ToolBridge(
        agent.execute_tool_unified,      # live wrapper = the shared funnel
        list,
    )

    results = [
        asyncio.run(bridge.execute("web_fetch", {"url": "http://x/a"}))
        for _ in range(3)
    ]
    assert agent._execute_tool_unified.executed == 2
    assert results[0] == "Error: connection timeout"
    assert results[1] == "Error: connection timeout"
    assert "repeated tool failure guard" in results[2]


def test_guard_counter_shared_between_classic_and_bridge(tmp_path):
    """The counter is per-RUN and shared: failures recorded through a ToolBridge
    block a later classic-loop call with the same identity, and vice versa."""
    agent = TitanAgent(
        llm=_SilentLLM(),
        memory=MemoryManager(tmp_path / "s2.db"),
        core_memory_path=tmp_path / "s2_core.db",
    )
    agent._execute_tool_unified = _FailingExec()
    bridge = ToolBridge(agent.execute_tool_unified, list)

    # Two failures through the structured funnel...
    for _ in range(2):
        asyncio.run(bridge.execute("web_fetch", {"url": "http://y/a"}))
    # ...the third identical call through the DIRECT wrapper is already blocked.
    result = asyncio.run(agent.execute_tool_unified("web_fetch", {"url": "http://y/a"}))
    assert "repeated tool failure guard" in result
    assert agent._execute_tool_unified.executed == 2