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