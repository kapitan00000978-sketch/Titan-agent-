"""
Phase 2 Tests: Reasoning Core (ReAct + Plan-and-Execute)
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from titan_agent.core.reasoning import (
    ActionType,
    Plan,
    PlanExecutor,
    PlanStep,
    ReActEngine,
    ReasoningConfig,
    ReasoningStep,
    ReasoningTrace,
    StepStatus,
)
from titan_agent.core.reasoning.interfaces import (
    ILLMProvider,
    IReflector,
    IToolExecutor,
)

# ---------- Mocks ----------

class MockLLM(ILLMProvider):
    """Scripted LLM that returns decisions in sequence."""

    def __init__(self, script: list[dict[str, Any]]):
        self.script = list(script)
        self.calls: list[tuple[list, float, int]] = []

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stream: bool = False,
    ):
        self.calls.append((messages, temperature, max_tokens))
        if not self.script:
            return '{"thought": "done", "action": "final_answer", "action_input": "complete"}'
        out = self.script.pop(0)
        return json.dumps(out) if isinstance(out, dict) else out

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ):
        raise NotImplementedError


class UnsupportedLLM(ILLMProvider):
    """LLM that only implements text completion."""

    def __init__(self, script: list[str]):
        self.script = list(script)

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stream: bool = False,
    ):
        if not self.script:
            return '{"thought": "done", "action": "final_answer", "action_input": "ok"}'
        return self.script.pop(0)

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ):
        raise NotImplementedError


class ScriptedLLM(ILLMProvider):
    """Tool-calling LLM using complete_with_tools."""

    def __init__(self, tool_script: list[dict[str, Any]]):
        self.tool_script = list(tool_script)

    async def complete(self, messages, temperature=0.3, max_tokens=4096, stream=False):
        return '{"thought": "x", "action": "final_answer", "action_input": "done"}'

    async def complete_with_tools(self, messages, tools, temperature=0.3, max_tokens=4096):
        if self.tool_script:
            return self.tool_script.pop(0)
        return {"content": "finished", "tool_calls": None}


class MockTools(IToolExecutor):
    def __init__(self, behavior: dict[str, Any] | None = None):
        self.behavior = behavior or {}
        self.calls: list[tuple[str, dict]] = []
        self._tools = [
            {
                "name": "search",
                "description": "Search the web",
                "function": {"name": "search", "description": "Search the web"},
            },
            {
                "name": "calculate",
                "description": "Do math",
                "function": {"name": "calculate", "description": "Do math"},
            },
        ]

    async def execute(self, tool_name: str, args: dict, context=None):
        self.calls.append((tool_name, args))
        if tool_name == "search":
            return "found results: titan agent"
        if tool_name == "calculate":
            return str(eval(str(args.get("expr", "0"))))
        return self.behavior.get(tool_name, "ok")

    def get_available_tools(self):
        return self._tools

    def has_tool(self, name: str) -> bool:
        return name in {"search", "calculate"}


class MockReflector(IReflector):
    def __init__(self, halt: bool = False):
        self.halt = halt
        self.calls = 0

    async def reflect(self, trace, focus=None):
        self.calls += 1
        return {"insight": "reconsider the approach", "halt": self.halt, "correction": None}

    async def should_continue(self, trace):
        return (not self.halt, "reflector decision")


# ---------- ReAct Tests ----------

class TestReActEngine:
    @pytest.mark.asyncio
    async def test_trivial_task(self):
        """Single-shot final answer."""
        llm = MockLLM([{"thought": "easy", "action": "final_answer", "action_input": "42"}])
        tools = MockTools()
        engine = ReActEngine(llm=llm, tools=tools)

        trace = await engine.reason("What is 6x7?")

        assert trace.final_answer == "42"
        assert any(s.action_type == ActionType.DECIDE for s in trace.steps)
        assert trace.completed_at is not None

    @pytest.mark.asyncio
    async def test_tool_loop(self):
        """Agent uses tools then answers."""
        llm = MockLLM(
            [
                {"thought": "need search", "action": "search", "action_input": {"q": "titan"}},
                {"thought": "got info", "action": "final_answer", "action_input": "Titan is powerful"},
            ]
        )
        tools = MockTools()
        engine = ReActEngine(llm=llm, tools=tools, config=ReasoningConfig(max_steps=5))

        trace = await engine.reason("Tell me about Titan")

        assert len(tools.calls) == 1
        assert tools.calls[0][0] == "search"
        assert trace.final_answer == "Titan is powerful"

    @pytest.mark.asyncio
    async def test_unknown_tool_error(self):
        """Unknown tool should produce a failed ACT step, not crash."""
        llm = MockLLM(
            [
                {"thought": "use bad", "action": "nonexistent_tool", "action_input": {}},
                {"thought": "recover", "action": "final_answer", "action_input": "recovered"},
            ]
        )
        tools = MockTools()
        engine = ReActEngine(llm=llm, tools=tools, config=ReasoningConfig(max_steps=10))

        trace = await engine.reason("test")

        failed_acts = [s for s in trace.steps if s.status == StepStatus.FAILED]
        assert failed_acts, "expected a failed ACT step"
        assert "Unknown tool" in (failed_acts[0].error or "")
        assert trace.final_answer == "recovered"

    @pytest.mark.asyncio
    async def test_max_steps_cap(self):
        """Engine must stop at max_steps."""
        # Always asks for tool - never finishes
        llm = MockLLM(
            [{"thought": "again", "action": "search", "action_input": {}}] * 100
        )
        tools = MockTools()
        engine = ReActEngine(llm=llm, tools=tools, config=ReasoningConfig(max_steps=3))

        steps = [s async for s in engine.stream_reason("never done")]
        final = steps[-1]

        assert final.status == StepStatus.FAILED
        assert "Max steps" in final.error
        assert len([s for s in steps if s.action_type == ActionType.ACT]) == 3

    @pytest.mark.asyncio
    async def test_reflection_called(self):
        """Reflector should be invoked on reflection interval."""
        llm = MockLLM(
            [
                {"thought": "s1", "action": "search", "action_input": {}},
                {"thought": "s2", "action": "search", "action_input": {}},
                {"thought": "s3", "action": "search", "action_input": {}},
                {"thought": "done", "action": "final_answer", "action_input": "fin"},
            ]
        )
        tools = MockTools()
        reflector = MockReflector()
        engine = ReActEngine(
            llm=llm,
            tools=tools,
            reflector=reflector,
            config=ReasoningConfig(max_steps=10, reflection_interval=3),
        )

        trace = await engine.reason("reflect test")

        assert reflector.calls >= 1
        reflect_steps = [s for s in trace.steps if s.action_type == ActionType.REFLECT]
        assert reflect_steps
        assert reflect_steps[0].status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_stream_yields_steps(self):
        llm = MockLLM(
            [
                {"thought": "search now", "action": "search", "action_input": {"q": "x"}},
                {"thought": "answer", "action": "final_answer", "action_input": "result"},
            ]
        )
        engine = ReActEngine(llm=llm, tools=MockTools())

        steps = [s async for s in engine.stream_reason("stream test")]

        types = [s.action_type for s in steps]
        assert ActionType.THINK in types
        assert ActionType.ACT in types
        assert ActionType.DECIDE in types
        assert steps[-1].content == "result"


# ---------- Plan And Execute Tests ----------

class TestPlanExecutor:
    @pytest.mark.asyncio
    async def test_create_plan_parses_steps(self):
        llm = MockLLM(
            [
                json.dumps(
                    {
                        "steps": [
                            {"description": "search for info", "tool_name": "search",
                             "tool_args": {"q": "x"}, "expected_outcome": "results", "dependencies": []},
                            {"description": "analyze", "tool_name": None, "tool_args": None,
                             "expected_outcome": "conclusion", "dependencies": ["step-1"]},
                        ]
                    }
                )
            ]
        )
        tools = MockTools()
        executor = PlanExecutor(llm=llm, tools=tools, config=ReasoningConfig())

        plan = await executor.create_plan("Research Titan Agent")

        assert isinstance(plan, Plan)
        assert len(plan.steps) == 2
        assert plan.steps[0].tool_name == "search"
        assert plan.goal == "Research Titan Agent"
        assert len(llm.calls) == 1

    @pytest.mark.asyncio
    async def test_create_plan_malformed_json(self):
        """Garbage output should not crash - empty steps."""
        llm = MockLLM(["this is not json at all"])
        executor = PlanExecutor(llm=llm, tools=MockTools())

        plan = await executor.create_plan("goal")

        assert plan.steps == []

    @pytest.mark.asyncio
    async def test_replan_preserves_completed(self):
        llm = MockLLM(
            [
                json.dumps(
                    {
                        "steps": [
                            {"description": "same step", "tool_name": None,
                             "tool_args": None, "expected_outcome": "ok", "dependencies": []}
                        ]
                    }
                )
            ]
        )
        executor = PlanExecutor(llm=llm, tools=MockTools())

        plan = Plan(goal="g")
        plan.add_step(PlanStep(description="same step", status=StepStatus.COMPLETED, result="done"))

        new_plan = await executor.replan(plan, context={"error": "failed"})

        assert new_plan.steps[0].status == StepStatus.COMPLETED
        assert new_plan.steps[0].result == "done"


# ---------- Types Tests ----------

class TestPlanTypes:
    def test_ready_steps_dependency_gating(self):
        plan = Plan(goal="g")
        s1 = PlanStep(description="first", status=StepStatus.PENDING)
        s2 = PlanStep(description="second", dependencies=[s1.step_id], status=StepStatus.PENDING)
        plan.add_step(s1)
        plan.add_step(s2)

        assert plan.get_ready_steps() == [s1]

        s1.status = StepStatus.COMPLETED
        assert plan.get_ready_steps() == [s2]

    def test_plan_complete(self):
        plan = Plan(goal="g")
        plan.add_step(PlanStep(description="a", status=StepStatus.COMPLETED))
        assert plan.is_complete()
        assert not plan.has_failed()

    def test_trace_step_numbering(self):
        trace = ReasoningTrace(task="t")
        trace.add_step(ReasoningStep(step_number=0))
        trace.add_step(ReasoningStep(step_number=0))
        assert trace.steps[0].step_number == 1
        assert trace.steps[1].step_number == 2
        assert trace.get_last_step() is trace.steps[-1]

    def test_trace_complete_detection(self):
        trace = ReasoningTrace(task="t", final_answer="answer")
        assert trace.is_complete()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])