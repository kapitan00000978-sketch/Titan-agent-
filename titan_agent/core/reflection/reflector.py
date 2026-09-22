"""
Self-Reflection - Reflexion-style critique and course correction.

- Reflector: LLM analyzes a reasoning trace and produces insights/corrections
- LessonStore: persistent experience memory (procedural lessons learned)
"""
from __future__ import annotations

from typing import Any

from ..memory import MemoryKind, MemoryRecord, MemorySystem
from ..reasoning.interfaces import ILLMProvider, IReflector, complete_text
from ..reasoning.types import ReasoningTrace, StepStatus

REFLECTION_PROMPT = """You are a self-reflection module. Given the reasoning trace of an
agent attempt, analyze what happened and produce concise actionable insights.

Trace for task: {task}
Steps:
{steps}

Respond with JSON STRICTLY in this shape:
{{
  "insight": "what went wrong / what pattern to notice (1-2 sentences)",
  "correction": "how the agent should change its approach (1-2 sentences)",
  "halt": false,
  "confidence": 0.8
}}
- "halt" = true ONLY if the task is provably impossible or already solved.
- "confidence" = how sure you are (0..1).
"""


class Reflector(IReflector):
    """LLM-driven self-reflection that corrects the agent's course."""

    def __init__(
        self,
        llm: ILLMProvider,
        lesson_store: LessonStore | None = None,
        max_trace_steps: int = 15,
    ):
        self.llm = llm
        self.lesson_store = lesson_store
        self.max_trace_steps = max_trace_steps
        self._reflection_count = 0

    async def reflect(
        self,
        trace: ReasoningTrace,
        focus: str | None = None,
    ) -> dict[str, Any]:
        if not trace.steps:
            return {"insight": "no steps to reflect on", "halt": True, "confidence": 1.0}

        self._reflection_count += 1
        steps_text = self._format_steps(trace)
        prompt = REFLECTION_PROMPT.format(
            task=trace.task[:1000],
            steps=steps_text,
        )
        if focus:
            prompt += f"\n\nFocus on: {focus}"

        raw = await complete_text(
            self.llm,
            messages=[
                {"role": "system", "content": "You output JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
        )
        result = self._parse_result(raw)
        result.setdefault("insight", "")
        result.setdefault("correction", "")
        result.setdefault("halt", False)
        result.setdefault("confidence", 0.5)

        # Persist a lesson if this reflection followed a failure
        if self.lesson_store and result.get("correction"):
            had_failure = any(
                s.status == StepStatus.FAILED for s in trace.steps[-5:]
            )
            if had_failure:
                self.lesson_store.record_lesson(
                    lesson=result["correction"],
                    context=trace.task,
                    metadata={
                        "insight": result.get("insight", ""),
                        "confidence": result.get("confidence", 0.5),
                        "reflection_count": self._reflection_count,
                    },
                )
        return result

    async def should_continue(
        self,
        trace: ReasoningTrace,
    ) -> tuple[bool, str]:
        """Default policy: continue unless a reflection marked halt=True.",
        """
        last_reflection = next(
            (
                s for s in reversed(trace.steps)
                if s.action_type.name == "REFLECT" and s.metadata.get("halt")
            ),
            None,
        )
        if last_reflection:
            return (False, last_reflection.content)
        return (True, "no halt signal")

    # ---------- Helpers ----------

    def _format_steps(self, trace: ReasoningTrace) -> str:
        lines = []
        for s in trace.steps[-self.max_trace_steps :]:
            status = s.status.value if s.status else "?"
            if s.action_type.name == "THINK":
                lines.append(f"- think: {s.content[:200]}")
            elif s.action_type.name == "ACT":
                tool_info = s.tool_name or "?"
                if s.error:
                    lines.append(f"- act[{status}]: {tool_info} ERROR: {s.error[:200]}")
                else:
                    result = str(s.tool_result or "")[:200]
                    lines.append(f"- act[{status}]: {tool_info} -> {result}")
            elif s.action_type.name == "REFLECT":
                lines.append(f"- reflect: {s.content[:200]}")
        return "\n".join(lines) or "(empty trace)"

    @staticmethod
    def _parse_result(raw: str) -> dict[str, Any]:
        import json

        text = str(raw)
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            return {}
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}


class LessonStore:
    """Persistent experience memory backed by MemorySystem (kind=PROCEDURAL)."""

    def __init__(self, memory: MemorySystem | None = None):
        self.memory = memory or MemorySystem()

    def record_lesson(
        self,
        lesson: str,
        context: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        """Save a lesson learned so future runs avoid the same mistake."""
        return self.memory.remember(
            content=lesson,
            kind=MemoryKind.PROCEDURAL,
            importance=min(1.0, 0.6 + (metadata or {}).get("confidence", 0.0) * 0.3),
            scope="lessons",
            metadata={**(metadata or {}), "context": context[:500]},
        )

    def get_relevant_lessons(self, context: str, limit: int = 3) -> list[MemoryRecord]:
        """Retrieve lessons relevant to the given context."""
        return self.memory.recall(
            query=context,
            kinds=[MemoryKind.PROCEDURAL],
            limit=limit,
            scope="lessons",
        )