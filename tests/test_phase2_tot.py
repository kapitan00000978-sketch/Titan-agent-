"""
Phase 2 Tests: Tree of Thoughts engine + LLM evaluator.
"""
from __future__ import annotations

import json

import pytest

from titan_agent.core.reasoning import (
    ActionType,
    LLMEvaluator,
    ReasoningConfig,
    ReasoningTrace,
    StepStatus,
    ToTEngine,
)
from titan_agent.core.reasoning.interfaces import IEvaluator, ILLMProvider


class ToTLLM(ILLMProvider):
    """Scripted LLM returning thought arrays from complete() calls."""

    def __init__(self, thoughts: list[list[str]]):
        self.thoughts = list(thoughts)
        self.calls: list[list] = []

    async def complete(self, messages, temperature=0.3, max_tokens=4096, stream=False):
        self.calls.append(messages)
        if not self.thoughts:
            return json.dumps(["final thought"])
        return json.dumps(self.thoughts.pop(0))

    async def complete_with_tools(self, messages, tools, temperature=0.3, max_tokens=4096):
        raise NotImplementedError


class ScriptedEvaluator(IEvaluator):
    """Evaluator that ranks candidates by a scoring keyword, then solves."""

    def __init__(self, solution_keyword: str = "ANSWER", solve_at_depth: int | None = None):
        self.solution_keyword = solution_keyword
        self.solve_at_depth = solve_at_depth
        self.solutions_checked = 0

    async def evaluate(self, trace, candidates):
        # Score by presence of the solution keyword, slightly randomized to
        # simulate real ranking (all deterministic here).
        scores = []
        for cand in candidates:
            last = cand.get_last_step()
            text = last.content if last else ""
            score = 1.0 if self.solution_keyword in text else (
                0.6 if text else 0.3
            )
            scores.append(score)
        return scores

    async def is_solution(self, trace, goal):
        self.solutions_checked += 1
        last = trace.get_last_step()
        solved = last is not None and self.solution_keyword in last.content
        if solved:
            trace.final_answer = last.content
        return solved, (1.0 if solved else 0.0)


class TestToTEngine:
    @pytest.mark.asyncio
    async def test_reason_finds_solution_path(self):
        """Beam search converges on the candidate containing the answer keyword."""
        llm = ToTLLM(
            [
                ["idea A", "idea B", "ANSWER idea C"],
                ["more A", "more B", "more C"],
            ]
        )
        evaluator = ScriptedEvaluator(solve_at_depth=1)
        engine = ToTEngine(
            llm=llm,
            evaluator=evaluator,
            config=ReasoningConfig(
                tot_branching_factor=3, tot_max_depth=3, temperature=0.4
            ),
        )

        trace = await engine.reason("solve the puzzle")

        assert trace.final_answer == "ANSWER idea C"
        assert trace.completed_at is not None
        # Path should contain the winning thought as a step
        contents = [s.content for s in trace.steps if s.action_type == ActionType.THINK]
        assert "ANSWER idea C" in contents

    @pytest.mark.asyncio
    async def test_no_solution_returns_best_path(self):
        llm = ToTLLM([["some idea", "another idea"]])
        evaluator = ScriptedEvaluator(solution_keyword="NEVER_FOUND")
        engine = ToTEngine(
            llm=llm,
            evaluator=evaluator,
            config=ReasoningConfig(tot_branching_factor=2, tot_max_depth=2),
        )

        trace = await engine.reason("task")

        assert trace.final_answer  # best path content
        assert trace.is_complete()

    @pytest.mark.asyncio
    async def test_stream_yields_depth_trace(self):
        llm = ToTLLM([["root a", "root b"]])
        evaluator = ScriptedEvaluator(solution_keyword="ANSWER")
        engine = ToTEngine(
            llm=llm,
            evaluator=evaluator,
            config=ReasoningConfig(tot_branching_factor=2, tot_max_depth=2),
        )

        steps = [s async for s in engine.stream_reason("stream task")]

        assert any(s.action_type == ActionType.PLAN for s in steps)
        types = {s.action_type for s in steps}
        assert ActionType.THINK in types
        assert steps[-1].status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_parse_malformed_thoughts(self):
        class GarbageLLM(ToTLLM):
            async def complete(self, messages, temperature=0.3, max_tokens=4096, stream=False):
                return "this is not a json array"

        engine = ToTEngine(
            llm=GarbageLLM([]),
            evaluator=ScriptedEvaluator(),
            config=ReasoningConfig(tot_branching_factor=2, tot_max_depth=1),
        )
        trace = await engine.reason("x")
        # Falls back to treating whole text as one idea; still completes
        assert trace.steps or trace.final_answer is not None


class TestLLMEvaluator:
    @pytest.mark.asyncio
    async def test_evaluate_parses_scores(self):
        class ScoreLLM(ILLMProvider):
            async def complete(self, messages, temperature=0.3, max_tokens=4096, stream=False):
                return "[0.1, 0.9, 0.5]"

            async def complete_with_tools(self, messages, tools, temperature=0.3, max_tokens=4096):
                raise NotImplementedError

        evaluator = LLMEvaluator(llm=ScoreLLM())
        candidates = []
        for i in range(3):
            t = ReasoningTrace(task="task")
            from titan_agent.core.reasoning import ReasoningStep

            t.add_step(
                ReasoningStep(action_type=ActionType.THINK, content=f"candidate {i}")
            )
            candidates.append(t)

        scores = await evaluator.evaluate(ReasoningTrace(task="task"), candidates)

        assert scores == [0.1, 0.9, 0.5]

    @pytest.mark.asyncio
    async def test_evaluate_pads_short_output(self):
        class ShortLLM(ILLMProvider):
            async def complete(self, messages, temperature=0.3, max_tokens=4096, stream=False):
                return "[0.8]"

            async def complete_with_tools(self, messages, tools, temperature=0.3, max_tokens=4096):
                raise NotImplementedError

        evaluator = LLMEvaluator(llm=ShortLLM())
        candidates = [
            ReasoningTrace(task="t", steps=[]),
            ReasoningTrace(task="t"),
            ReasoningTrace(task="t"),
        ]
        scores = await evaluator.evaluate(ReasoningTrace(task="t"), candidates)
        assert len(scores) == 3
        assert scores[0] == pytest.approx(0.8)  # first stays 0.8
        assert scores[1] == pytest.approx(0.5)  # padded

    @pytest.mark.asyncio
    async def test_is_solution_detects(self):
        class SolveLLM(ILLMProvider):
            async def complete(self, messages, temperature=0.3, max_tokens=4096, stream=False):
                return '{"solved": true, "confidence": 0.95, "answer": "the answer is 42"}'

            async def complete_with_tools(self, messages, tools, temperature=0.3, max_tokens=4096):
                raise NotImplementedError

        evaluator = LLMEvaluator(llm=SolveLLM())
        trace = ReasoningTrace(task="what is the answer")
        from titan_agent.core.reasoning import ReasoningStep

        trace.add_step(ReasoningStep(action_type=ActionType.THINK, content="thinking"))

        solved, confidence = await evaluator.is_solution(trace, "what is the answer")

        assert solved is True
        assert confidence == pytest.approx(0.95)
        assert trace.final_answer == "the answer is 42"

    @pytest.mark.asyncio
    async def test_is_solution_not_solved(self):
        class NoLLM(ILLMProvider):
            async def complete(self, messages, temperature=0.3, max_tokens=4096, stream=False):
                return '{"solved": false, "confidence": 0.2, "answer": ""}'

            async def complete_with_tools(self, messages, tools, temperature=0.3, max_tokens=4096):
                raise NotImplementedError

        evaluator = LLMEvaluator(llm=NoLLM())
        trace = ReasoningTrace(task="t")
        solved, _ = await evaluator.is_solution(trace, "t")
        assert solved is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])