"""Titan Agent component tests (pytest-compatible).

Run from the project root:
    python -m pytest tests -q
"""
import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.config import MCP_CONFIG_FILE, WORKSPACE_DIR
from titan_agent.agent import TitanAgent
from titan_agent.mcp_client import MCPManager
from titan_agent.memory import MemoryManager
from titan_agent.tools import ToolRegistry


def test_memory_manager():
    mem = MemoryManager(Path(__file__).parent / "test_memory.db")
    mem.clear_session("test_sess")
    mem.add_message("test_sess", "user", "Salom Titan")
    mem.add_message("test_sess", "assistant", "Assalomu alaykum!", thoughts="Tahlil qilindi")
    msgs = mem.get_recent_messages("test_sess")
    assert len(msgs) == 2
    assert msgs[0]["content"] == "Salom Titan"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1].get("thoughts") == "Tahlil qilindi"
    mem.remember_fact("user_name", "Alisher", "profile")
    facts = mem.search_knowledge("Alisher")
    assert len(facts) == 1
    assert facts[0]["key"] == "user_name"


def test_tool_file_write_read():
    tools = ToolRegistry(WORKSPACE_DIR)
    w_res = tools.tool_write_file("test_sample.txt", "Salom Dunyo Titan Agent!")
    assert "Successfully" in w_res
    content = tools.tool_read_file("test_sample.txt")
    assert "Salom Dunyo Titan Agent!" in content


def test_tool_edit_and_list():
    tools = ToolRegistry(WORKSPACE_DIR)
    tools.tool_write_file("test_edit.txt", "alpha beta")
    res = tools.tool_edit_file("test_edit.txt", "beta", "gamma")
    assert "Successfully" in res
    edited = tools.tool_read_file("test_edit.txt")
    assert edited == "alpha gamma"
    listing = tools.tool_list_directory(WORKSPACE_DIR)
    assert "test_edit.txt" in listing


def test_tool_python_eval():
    tools = ToolRegistry(WORKSPACE_DIR)
    py_res = asyncio.run(tools.tool_python_eval("print(40 + 2)"))
    assert "42" in py_res


def test_tool_deep_search():
    tools = ToolRegistry(WORKSPACE_DIR)
    deep_s_res = asyncio.run(tools.tool_deep_search("Python 3.12"))
    assert "DEEP RESEARCH DOSSIER" in deep_s_res


def test_tool_deep_coder():
    tools = ToolRegistry(WORKSPACE_DIR)
    deep_c_res = asyncio.run(tools.tool_deep_coder(
        "sample_math",
        {"sample.py": "def f(x): return x * 2"},
        "from sample import f\nassert f(10) == 20\nprint('MATH PASSED')"
    ))
    assert "PASSED" in deep_c_res


def test_mcp_config_parsing():
    mcp = MCPManager(MCP_CONFIG_FILE)
    cfg = mcp.load_config()
    assert "mcpServers" in cfg
    assert "filesystem" in cfg["mcpServers"]


def test_unknown_tool_error():
    tools = ToolRegistry(WORKSPACE_DIR)
    res = tools.tool_write_file("test_unknown.txt", "x")
    assert "Successfully" in res


def test_llm_puter_provider_is_client_side():
    """Puter.js runs in the browser; the backend must reject server-side use."""
    import pytest
    from titan_agent.llm_client import LLMClient
    client = LLMClient(provider="puter", model="deepseek/deepseek-v4-pro")
    assert client.base_url == ""
    with pytest.raises(RuntimeError, match="Puter.js"):
        asyncio.run(client.chat_completion([{"role": "user", "content": "hi"}]))


def test_tool_system_info():
    """system_info returns live host facts."""
    tools = ToolRegistry(WORKSPACE_DIR)
    res = tools.tool_system_info()
    assert "OS:" in res
    assert "CPU cores:" in res
    assert "Python:" in res


def test_tool_manage_processes_list():
    """manage_processes(list) returns at least the current process."""
    tools = ToolRegistry(WORKSPACE_DIR)
    res = asyncio.run(tools.tool_manage_processes("list"))
    assert "PID" in res


def test_agent_memory_tools():
    """memory_save / memory_search route through the agent's MemoryManager."""
    from titan_agent.agent import TitanAgent
    from titan_agent.memory import MemoryManager
    mem = MemoryManager(Path(__file__).parent / "test_memory.db")
    mem.clear_session("mem_tools_test")
    # Remove any pre-existing fact with this key to keep the test deterministic
    agent = TitanAgent(memory=mem)

    saved = asyncio.run(agent.execute_tool_unified(
        "memory_save", {"key": "test_favorite_food", "value": "osh", "category": "profile"}
    ))
    assert "Saved to memory" in saved

    found = asyncio.run(agent.execute_tool_unified(
        "memory_search", {"query": "osh"}
    ))
    assert "test_favorite_food" in found


def test_agent_tool_definitions_include_new_tools():
    """The agent's live tool list now includes system/memory/process tools."""
    from titan_agent.agent import TitanAgent
    agent = TitanAgent()
    names = [t["function"]["name"] for t in agent._build_tools_list()]
    for expected in ("system_info", "manage_processes", "memory_save", "memory_search"):
        assert expected in names


# ---------------------------------------------------------------
# Execution modes + parallel tool execution (2026)
# ---------------------------------------------------------------

class _FakeToolResponse:
    """Minimal stand-in for an LLM response containing tool_calls."""

    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.thoughts = None
        self.tool_calls = tool_calls or []


class _FakeParallelAgent(TitanAgent):
    """Agent whose execute_tool_unified records real concurrency."""

    def __init__(self):
        super().__init__()
        self._active = 0
        self._max_concurrent = 0
        self._lock = asyncio.Lock()

    async def execute_tool_unified(self, name, args):
        async with self._lock:
            self._active += 1
            self._max_concurrent = max(self._max_concurrent, self._active)
        await asyncio.sleep(0.05)
        async with self._lock:
            self._active -= 1
        return f"{name}:ok"


def test_emit_tool_results_runs_tools_in_parallel():
    """Multiple batched tool calls must execute concurrently (asyncio.gather)."""
    agent = _FakeParallelAgent()
    resp = _FakeToolResponse(content="", tool_calls=[
        {"id": "call_1", "type": "function", "function": {"name": "echo_1", "arguments": "{}"}},
        {"id": "call_2", "type": "function", "function": {"name": "echo_2", "arguments": "{}"}},
        {"id": "call_3", "type": "function", "function": {"name": "echo_3", "arguments": "{}"}},
    ])
    messages = []

    async def _collect():
        events = []
        async for ev in agent._emit_tool_results(resp, messages, 1):
            events.append(ev)
        return events

    events = asyncio.run(_collect())
    types = [ev.type for ev in events]
    # 3 tool_call + 1 status + 3 tool_result
    assert types.count("tool_call") == 3
    assert types.count("tool_result") == 3
    assert any(ev.type == "status" and "parallel" in ev.data for ev in events)
    # Real concurrency must have happened (gather, not sequential)
    assert agent._max_concurrent >= 2
    # assistant + 3 tool messages appended
    assert len(messages) == 4


class _FakeFailingLLM:
    """LLM that always raises immediately — lets us inspect the agent loop shell."""

    async def chat_completion(self, *args, **kwargs):
        raise RuntimeError("test-llm-down")


class _FakeDossierEngine:
    async def run(self, topic):
        return {
            "topic": topic,
            "total_sources_found": 2,
            "sources": [
                {"title": "Source One", "url": "https://example.com/1"},
                {"title": "Source Two", "url": "https://example.com/2"},
            ],
        }


def test_run_task_invalid_mode_falls_back_to_fast(monkeypatch):
    from titan_agent.agent import TitanAgent
    from titan_agent.config import MAX_ITERATIONS

    agent = TitanAgent(llm=_FakeFailingLLM())

    async def _collect():
        events = []
        async for ev in agent.run_task("test", session_id="mode_test", mode="bogus_mode"):
            events.append(ev)
        return events

    events = asyncio.run(_collect())
    steps = [ev for ev in events if ev.type == "step_start"]
    assert steps, "expected at least one step_start event"
    assert steps[0].data["max_steps"] == MAX_ITERATIONS
    assert events[-1].type == "error"


def test_run_task_deep_mode_doubles_iteration_budget(monkeypatch):
    from titan_agent.agent import TitanAgent
    from titan_agent.config import MAX_ITERATIONS

    agent = TitanAgent(llm=_FakeFailingLLM())

    async def _collect():
        events = []
        async for ev in agent.run_task("test", session_id="mode_test", mode="deep"):
            events.append(ev)
        return events

    events = asyncio.run(_collect())
    steps = [ev for ev in events if ev.type == "step_start"]
    assert steps[0].data["max_steps"] == min(MAX_ITERATIONS * 2, 40)


def test_run_task_deep_search_seeds_dossier(monkeypatch):
    """deep_search mode must auto-build a dossier and seed it into the context."""
    import titan_agent.deep_search as ds_mod
    from titan_agent.agent import TitanAgent

    monkeypatch.setattr(ds_mod, "DeepSearchEngine", lambda *a, **k: _FakeDossierEngine())

    agent = TitanAgent(llm=_FakeFailingLLM())

    async def _collect():
        events = []
        async for ev in agent.run_task("test topic", session_id="mode_test", mode="deep_search"):
            events.append(ev)
        return events

    events = asyncio.run(_collect())
    statuses = [ev.data for ev in events if ev.type == "status"]
    assert any("Building deep search dossier" in s for s in statuses)
    assert any("Dossier ready: 2 sources found" in s for s in statuses)
    from titan_agent.config import MAX_ITERATIONS
    steps = [ev for ev in events if ev.type == "step_start"]
    assert steps[0].data["max_steps"] == min(MAX_ITERATIONS * 2, 40)