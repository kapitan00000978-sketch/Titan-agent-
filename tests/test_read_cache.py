"""Test Phase 39: In-Run Idempotent Read Caching in TitanAgent."""
import asyncio
import pytest
from titan_agent.agent import TitanAgent
from titan_agent.llm_client import LLMResponse


@pytest.mark.asyncio
async def test_read_cache_hit_and_invalidation(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("initial content", encoding="utf-8")

    read_calls = 0

    class CountingAgent(TitanAgent):
        async def _execute_tool_unified(self, name: str, args: dict):
            nonlocal read_calls
            if name == "read_file":
                read_calls += 1
                return f.read_text(encoding="utf-8")
            if name == "write_file":
                f.write_text(args["content"], encoding="utf-8")
                return "File written"
            return await super()._execute_tool_unified(name, args)

    agent = CountingAgent()

    # 1. First read -> executes
    res1 = await agent.execute_tool_unified("read_file", {"path": str(f)})
    assert res1 == "initial content"
    assert read_calls == 1

    # 2. Second read with same args -> returned from cache (read_calls remains 1)
    res2 = await agent.execute_tool_unified("read_file", {"path": str(f)})
    assert res2 == "initial content"
    assert read_calls == 1

    # 3. Mutating write -> invalidates read cache
    await agent.execute_tool_unified("write_file", {"path": str(f), "content": "updated content"})
    assert len(agent._read_cache) == 0

    # 4. Third read -> cache miss, re-executes handler
    res3 = await agent.execute_tool_unified("read_file", {"path": str(f)})
    assert res3 == "updated content"
    assert read_calls == 2
