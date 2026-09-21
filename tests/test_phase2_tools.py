"""
Phase 2 Tests: Tool Registry (discovery, policy, composition, sandbox)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from titan_agent.core.guardrails import PolicyEngine
from titan_agent.core.reasoning import (
    ActionType,
    ReActEngine,
    ReasoningConfig,
    StepStatus,
)
from titan_agent.core.reasoning.interfaces import ILLMProvider
from titan_agent.core.tools import RiskLevel, ToolCategory, ToolRegistry


class FakeDelegate:
    """Mimics tools.ToolRegistry shape: get_tool_definitions + tool_* handlers."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def get_tool_definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Reads a file from the filesystem",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string", "description": "file path"}},
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": "Executes a shell command",
                    "parameters": {
                        "type": "object",
                        "properties": {"command": {"type": "string"}},
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Searches the web",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "take_screenshot",
                    "description": "Captures the screen (PC control)",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    async def tool_read_file(self, path: str) -> str:
        self.calls.append(("read_file", {"path": path}))
        return f"content of {path}"

    async def tool_execute_command(self, command: str) -> str:
        self.calls.append(("execute_command", {"command": command}))
        return f"ran: {command}"

    async def tool_web_search(self, query: str) -> str:
        self.calls.append(("web_search", {"query": query}))
        return "web results for: " + query

    async def tool_take_screenshot(self) -> str:
        self.calls.append(("take_screenshot", {}))
        return "screenshot saved"


class StubLLM(ILLMProvider):
    """ReAct-compatible LLM that always defers to tools then answers."""

    def __init__(self, steps: list[dict]):
        self.steps = list(steps)

    async def complete(self, messages, temperature=0.3, max_tokens=4096, stream=False):
        step = self.steps.pop(0) if self.steps else {
            "thought": "done", "action": "final_answer", "action_input": "finished"
        }
        import json

        return json.dumps(step)

    async def complete_with_tools(self, messages, tools, temperature=0.3, max_tokens=4096):
        raise NotImplementedError


@pytest.fixture()
def registry(tmp_path: Path):
    return ToolRegistry(
        delegate=FakeDelegate(),
        policy=PolicyEngine(),
        workspace=tmp_path,
        require_approval_for=["take_screenshot"],
    )


class TestDiscovery:
    def test_all_tools_registered(self, registry):
        assert registry.stats()["total"] == 4
        names = {s.name for s in registry.all_specs()}
        assert names == {"read_file", "execute_command", "web_search", "take_screenshot"}

    def test_search_by_keyword(self, registry):
        hits = registry.discover("search")
        assert [s.name for s in hits] == ["web_search"]

    def test_search_by_category(self, registry):
        hits = registry.discover(category=ToolCategory.FILESYSTEM)
        assert [s.name for s in hits] == ["read_file"]

    def test_risk_classification(self, registry):
        spec = registry.get("execute_command")
        assert spec.risk == RiskLevel.MEDIUM
        assert registry.get("read_file").risk == RiskLevel.LOW

    def test_risk_ceiling(self, registry):
        hits = registry.discover(max_risk=RiskLevel.LOW)
        assert all(s.risk == RiskLevel.LOW for s in hits)

    def test_openai_schema_output(self, registry):
        schema = registry.get_available_tools()
        assert schema[0]["type"] == "function"
        assert "name" in schema[0]["function"]
        assert "parameters" in schema[0]["function"]


class TestExecution:
    @pytest.mark.asyncio
    async def test_execute_ok(self, registry):
        result = await registry.execute("read_file", {"path": "notes.txt"}, context={})
        assert "content of" in result
        # Sandbox resolved the relative path inside the workspace
        assert registry.delegate.calls[-1][0] == "read_file"
        assert "notes.txt" in registry.delegate.calls[-1][1]["path"]
        assert Path(registry.delegate.calls[-1][1]["path"]).is_absolute()

    @pytest.mark.asyncio
    async def test_unknown_tool_rejected(self, registry):
        with pytest.raises(LookupError):
            await registry.execute("not_a_tool", {})

    @pytest.mark.asyncio
    async def test_policy_blocks_destructive(self, registry):
        with pytest.raises(PermissionError):
            await registry.execute("execute_command", {"command": "rm -rf /"})

    @pytest.mark.asyncio
    async def test_policy_allows_safe_command(self, registry):
        result = await registry.execute("execute_command", {"command": "dir"})
        assert "dir" in result

    @pytest.mark.asyncio
    async def test_approval_required(self, registry):
        with pytest.raises(PermissionError, match="approval"):
            await registry.execute("take_screenshot", {})

    @pytest.mark.asyncio
    async def test_sandbox_rejects_outside_path(self, registry, tmp_path: Path):
        outside = str(tmp_path.parent / "escape.txt")
        with pytest.raises(PermissionError, match="outside"):
            await registry.execute("read_file", {"path": outside})

    @pytest.mark.asyncio
    async def test_sandbox_allows_inside(self, registry, tmp_path: Path):
        inside = str(tmp_path / "ok.txt")
        result = await registry.execute("read_file", {"path": inside})
        assert "content of" in result
        # path got resolved relative to workspace
        assert registry.delegate.calls[-1][1]["path"] == inside


class TestComposition:
    @pytest.mark.asyncio
    async def test_compose_chains_results(self, registry):
        steps = [
            ("web_search", {"query": "titan agent"}),
            ("read_file", {"path": {"$result": 0}}),
        ]
        outputs = await registry.compose(steps)
        assert len(outputs) == 2
        # read_file received web results text as (sandbox-resolved) path
        read_calls = [call for call in registry.delegate.calls if call[0] == "read_file"]
        assert read_calls
        assert "web results" in read_calls[-1][1]["path"]

    @pytest.mark.asyncio
    async def test_parallel_runs_all(self, registry):
        outputs = await registry.run_parallel(
            [
                ("web_search", {"query": "a"}),
                ("web_search", {"query": "b"}),
            ]
        )
        assert len(outputs) == 2
        assert all("web results" in o for o in outputs)


class TestReActIntegration:
    """Capstone: ReAct engine drives the policy-guarded tool registry."""

    @pytest.mark.asyncio
    async def test_react_uses_policy_tools(self, registry):
        llm = StubLLM(
            [
                {"thought": "search first", "action": "web_search", "action_input": {"query": "titan"}},
                {"thought": "answer now", "action": "final_answer", "action_input": "Titan is great"},
            ]
        )
        engine = ReActEngine(llm=llm, tools=registry, config=ReasoningConfig(max_steps=5))
        trace = await engine.reason("research titan")

        assert trace.final_answer == "Titan is great"
        assert registry.delegate.calls[0][0] == "web_search"
        act_steps = [s for s in trace.steps if s.action_type == ActionType.ACT]
        assert all(s.status == StepStatus.COMPLETED for s in act_steps)

    @pytest.mark.asyncio
    async def test_react_recovers_from_policy_denial(self, registry):
        """Blocked tool becomes an observation; agent recovers with another tool."""
        llm = StubLLM(
            [
                {"thought": "try rm", "action": "execute_command", "action_input": {"command": "rm -rf /"}},
                {"thought": "blocked, use search", "action": "web_search", "action_input": {"query": "fallback"}},
                {"thought": "done", "action": "final_answer", "action_input": "recovered"},
            ]
        )
        engine = ReActEngine(llm=llm, tools=registry, config=ReasoningConfig(max_steps=8))
        trace = await engine.reason("test policy")

        failed = [s for s in trace.steps if s.status == StepStatus.FAILED]
        assert failed, "policy denial should surface as a failed ACT step"
        assert trace.final_answer == "recovered"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])