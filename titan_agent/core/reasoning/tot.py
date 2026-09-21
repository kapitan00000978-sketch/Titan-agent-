"""
Tree of Thoughts Engine - beam-search over multiple reasoning paths.

Implements the ToT pattern (Yao et al.) with:
- Branching: LLM generates multiple candidate next-thoughts per node
- Expansion: each node's thoughts are extended level by level
- Evaluation: IEvaluator scores candidate paths (LLM or heuristic)
- Pruning: top-k beam selection keeps the most promising paths
- Solution detection: stops early when a path solves the goal
"""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from .interfaces import IEvaluator, ILLMProvider, IReasoningEngine, ReasoningContext
from .types import (
    ActionType,
    ReasoningConfig,
    ReasoningStep,
    ReasoningTrace,
    StepStatus,
)

GENERATE_PROMPT = """You are exploring multiple solution paths for a problem.

Problem: {task}

Progress so far:
{path}

Generate exactly {count} DISTINCT, DIFFERENT next-step ideas that each advance toward
solving the problem. The ideas should cover different strategies, not variations of
one idea.

Respond with ONLY a JSON array of strings, e.g. ["idea one", "idea two", "idea three"].
"""

EVALUATE_PROMPT = """You are a careful evaluator. Score how promising each candidate
solution path is for solving the task below.

Task: {task}

Candidates:
{candidates}

Respond with ONLY a JSON array of numbers between 0 and 1 (one per candidate),
e.g. [0.2, 0.8, 0.5]. Higher = more likely to lead to a correct solution.
"""

SOLUTION_PROMPT = """Determine whether the following path completely solves the task.

Task: {task}

Path:
{path}

Respond with ONLY JSON:
{{"solved": true|false, "confidence": 0.0..1.0, "answer": "the final answer if solved, else empty string"}}
"""


class LLMEvaluator(IEvaluator):
    """Concrete IEvaluator powered by an LLM."""

    def __init__(self, llm: ILLMProvider, temperature: float = 0.2):
        self.llm = llm
        self.temperature = temperature

    async def evaluate(
        self,
        trace: ReasoningTrace,
        candidates: list[ReasoningTrace],
    ) -> list[float]:
        if not candidates:
            return []
        if len(candidates) == 1:
            return [0.5]
        numbered = "\n".join(
            f"{i + 1}. {c.get_last_step().content if c.get_last_step() else '(empty)'}"
            for i, c in enumerate(candidates)
        )
        raw = await self.llm.complete(
            messages=[
                {"role": "system", "content": "You output JSON only."},
                {"role": "user", "content": EVALUATE_PROMPT.format(
                    task=trace.task[:1500], candidates=numbered
                )},
            ],
            temperature=self.temperature,
            max_tokens=500,
        )
        scores = self._parse_score_list(raw)
        # Pad/trim to candidate count
        if len(scores) > len(candidates):
            scores = scores[: len(candidates)]
        while len(scores) < len(candidates):
            scores.append(0.5)
        return [max(0.0, min(1.0, s)) for s in scores]

    async def is_solution(
        self,
        trace: ReasoningTrace,
        goal: str,
    ) -> tuple[bool, float]:
        last = trace.get_last_step()
        path_text = last.content if last else "(empty path)"
        raw = await self.llm.complete(
            messages=[
                {"role": "system", "content": "You output JSON only."},
                {"role": "user", "content": SOLUTION_PROMPT.format(
                    task=goal[:1500], path=path_text[:3000]
                )},
            ],
            temperature=0.0,
            max_tokens=300,
        )
        data = self._parse_dict(raw)
        solved = bool(data.get("solved", False))
        confidence = float(data.get("confidence", 1.0 if solved else 0.0))
        if solved:
            trace.final_answer = str(data.get("answer", "") or last.content)
        return solved, confidence

    @staticmethod
    def _parse_score_list(raw: str) -> list[float]:
        text = str(raw)
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end <= start:
            return []
        try:
            data = json.loads(text[start : end + 1])
            return [float(x) for x in data]
        except (json.JSONDecodeError, TypeError, ValueError):
            return []

    @staticmethod
    def _parse_dict(raw: str) -> dict[str, Any]:
        text = str(raw)
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            return {}
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}


class ToTEngine(IReasoningEngine):
    """Beam-search reasoning over multiple candidate thought paths."""

    def __init__(
        self,
        llm: ILLMProvider,
        evaluator: IEvaluator,
        config: ReasoningConfig | None = None,
    ):
        self.llm = llm
        self.evaluator = evaluator
        self.config = config or ReasoningConfig()
        self._context = ReasoningContext(config=self.config, llm=llm, evaluator=evaluator)

    # ---------- IReasoningEngine ----------

    async def reason(
        self,
        task: str,
        config: ReasoningConfig | None = None,
        trace: ReasoningTrace | None = None,
    ) -> ReasoningTrace:
        if config:
            self.config = config
            self._context.config = config
        self._context = ReasoningContext(
            config=self.config, llm=self.llm, evaluator=self.evaluator
        )
        best = await self._beam_search(task)
        best.completed_at = self._utcnow()
        return best

    async def stream_reason(
        self,
        task: str,
        config: ReasoningConfig | None = None,
    ) -> AsyncGenerator[ReasoningStep, None]:
        if config:
            self.config = config
            self._context.config = config
        current = ReasoningTrace(task=task)
        current.steps = []
        beam: list[ReasoningTrace] = [current]

        for depth in range(1, self.config.tot_max_depth + 1):
            yield ReasoningStep(
                action_type=ActionType.PLAN,
                content=f"ToT depth {depth}: expanding {len(beam)} path(s)",
                status=StepStatus.COMPLETED,
            )
            expanded = await self._expand_level(beam, task)
            if not expanded:
                break
            beam = await self._prune(expanded, task)

            for cand in beam:
                step = cand.get_last_step()
                if step:
                    step.step_number = depth
                    step.status = StepStatus.COMPLETED
                    yield step

            solved = await self._find_solution(beam, task)
            if solved is not None:
                yield ReasoningStep(
                    action_type=ActionType.DECIDE,
                    content=solved.final_answer or solved.get_last_step().content,
                    status=StepStatus.COMPLETED,
                )
                return

        if beam:
            best = beam[0]
            best.completed_at = self._utcnow()
            yield ReasoningStep(
                action_type=ActionType.DECIDE,
                content=best.final_answer
                or (best.get_last_step().content if best.get_last_step() else "No solution found"),
                status=StepStatus.COMPLETED,
            )

    # ---------- Core algorithm ----------

    async def _beam_search(self, task: str) -> ReasoningTrace:
        root = ReasoningTrace(task=task)
        root.steps = []
        beam: list[ReasoningTrace] = [root]

        for _depth in range(self.config.tot_max_depth):
            expanded = await self._expand_level(beam, task)
            if not expanded:
                break
            beam = await self._prune(expanded, task)
            solved = await self._find_solution(beam, task)
            if solved is not None:
                return solved

        if beam:
            best = beam[0]
            if not best.final_answer:
                last = best.get_last_step()
                best.final_answer = last.content if last else "No solution found"
            best.completed_at = self._utcnow()
            return best
        trace = ReasoningTrace(task=task)
        trace.completed_at = self._utcnow()
        return trace

    async def _expand_level(
        self,
        beam: list[ReasoningTrace],
        task: str,
    ) -> list[ReasoningTrace]:
        """For each path, generate `b` next thoughts -> new candidate traces."""
        expanded: list[ReasoningTrace] = []
        for path in beam:
            path_text = " -> ".join(
                s.content for s in path.steps if s.content
            ) or "(no progress yet)"
            thoughts = await self._generate_thoughts(task, path_text)
            for thought in thoughts[: self.config.tot_branching_factor]:
                new_trace = path.model_copy(deep=True)
                new_trace.steps = [s for s in path.steps]  # keep lineage
                new_trace.add_step(
                    ReasoningStep(
                        action_type=ActionType.THINK,
                        content=thought,
                        status=StepStatus.COMPLETED,
                    )
                )
                expanded.append(new_trace)
        return expanded

    async def _prune(
        self,
        expanded: list[ReasoningTrace],
        task: str,
    ) -> list[ReasoningTrace]:
        """Score candidates via the evaluator and keep the top beam width."""
        root = ReasoningTrace(task=task)
        scores = await self.evaluator.evaluate(root, expanded)
        ranked = sorted(
            zip(expanded, scores), key=lambda pair: pair[1], reverse=True
        )
        keep = ranked[: self.config.tot_branching_factor]
        pruned: list[ReasoningTrace] = []
        for cand, score in keep:
            # Record the score in metadata - NOT as a trace step, so the
            # candidate path stays clean for solution detection.
            cand.metadata["tot_score"] = score
            pruned.append(cand)
        return pruned

    async def _find_solution(
        self,
        beam: list[ReasoningTrace],
        task: str,
    ) -> ReasoningTrace | None:
        """Return the first candidate the evaluator considers a solution."""
        for cand in beam:
            try:
                solved, _confidence = await self.evaluator.is_solution(cand, task)
            except Exception:  # noqa: BLE001 - evaluator failures skip the candidate
                solved = False
            if solved:
                cand.completed_at = self._utcnow()
                return cand
        return None

    async def _generate_thoughts(self, task: str, path_text: str, ) -> list[str]:
        """Ask the LLM for distinct next-step ideas (JSON array of strings)."""
        raw = await self.llm.complete(
            messages=[
                {"role": "system", "content": "You output JSON only."},
                {"role": "user", "content": GENERATE_PROMPT.format(
                    task=task[:1500],
                    path=path_text[:2000],
                    count=self.config.tot_branching_factor,
                )},
            ],
            temperature=self.config.temperature,
            max_tokens=min(self.config.max_thinking_tokens, 2000),
        )
        return self._parse_string_list(raw)

    @staticmethod
    def _parse_string_list(raw: str) -> list[str]:
        text = str(raw)
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end <= start:
            # Fallback: whole text as a single idea
            cleaned = text.strip().strip('"')
            return [cleaned] if cleaned else []
        try:
            data = json.loads(text[start : end + 1])
            return [str(x).strip() for x in data if str(x).strip()]
        except (json.JSONDecodeError, TypeError):
            return [text.strip()] if text.strip() else []

    @staticmethod
    def _utcnow():
        from datetime import datetime, timezone

        return datetime.now(timezone.utc)