"""
Plan-and-Execute Engine - decompose a goal into dependency-aware steps.

Features:
- LLM-driven plan creation with tool awareness
- Dependency graph (steps only run when deps are met)
- Replanning on failure (fixed step fallback)
- Step state tracking with retries
"""
from __future__ import annotations

import json
from typing import Any

from .interfaces import ILLMProvider, IPlanner, IToolExecutor, complete_text
from .types import Plan, PlanStep, ReasoningConfig, StepStatus

PLAN_PROMPT = """You are a meticulous planning engine. Given a goal and a set of tools,
produce a JSON plan that decomposes the goal into ordered, dependency-aware steps.

Rules:
1. Each step must be concrete and actionable with the available tools.
2. Use "tool_name": null for pure reasoning/analysis steps.
3. "dependencies" is a list of step_ids the step depends on ([] for first steps).
4. Keep the plan minimal - merge steps that can be done together.
5. "expected_outcome" must be a verifiable statement.

Tool list:
{tools}

Goal: {goal}

Respond with ONLY JSON:
{{
  "steps": [
    {{
      "description": "what to do",
      "tool_name": "tool or null",
      "tool_args": {{...}} or null,
      "expected_outcome": "verifiable result",
      "dependencies": []
    }}
  ]
}}
"""


class PlanExecutor(IPlanner):
    """Creates and updates execution plans."""

    def __init__(
        self,
        llm: ILLMProvider,
        tools: IToolExecutor | None = None,
        config: ReasoningConfig | None = None,
    ):
        self.llm = llm
        self.tools = tools
        self.config = config or ReasoningConfig()

    # ---------- IPlanner API ----------

    async def create_plan(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        available_tools: list[dict[str, Any]] | None = None,
    ) -> Plan:
        tools = (available_tools or (self.tools.get_available_tools() if self.tools else [])) or []
        tools_desc = "\n".join(
            f"- {t.get('name', t.get('function', {}).get('name', 'unknown'))}: "
            f"{t.get('description', t.get('function', {}).get('description', ''))}"
            for t in tools
        )
        prompt = PLAN_PROMPT.format(tools=tools_desc or "(no tools)", goal=goal)
        if context:
            prompt += f"\n\nContext:\n{json.dumps(context, default=str)[:4000]}"

        raw = await complete_text(
            self.llm,
            messages=[
                {"role": "system", "content": "You output JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=min(self.config.max_plan_steps * 250, 8000),
        )
        data = self._parse_plan(raw)

        plan = Plan(goal=goal)
        for item in data.get("steps", [])[: self.config.max_plan_steps]:
            plan.add_step(
                PlanStep(
                    description=str(item.get("description", "")).strip(),
                    tool_name=item.get("tool_name"),
                    tool_args=item.get("tool_args"),
                    expected_outcome=str(item.get("expected_outcome", "")),
                    dependencies=[str(d) for d in (item.get("dependencies") or [])],
                    max_retries=self.config.max_retries_per_step,
                )
            )
        return plan

    async def replan(
        self,
        plan: Plan,
        failed_step: PlanStep | None = None,
        error: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> Plan:
        """Recreate the plan based on failure context, preserving completed steps."""
        candidate = await self.create_plan(
            plan.goal,
            context={
                **(context or {}),
                "previous_plan": [s.model_dump() for s in plan.steps],
                "failed_step": failed_step.dict() if failed_step else None,
                "error": error,
            },
        )
        # Preserve already-completed steps from the old plan
        completed = {s.description: s for s in plan.steps if s.status == StepStatus.COMPLETED}
        for step in candidate.steps:
            if step.description in completed:
                step.status = StepStatus.COMPLETED
                step.result = completed[step.description].result
        return candidate

    # ---------- Helpers ----------

    def _parse_plan(self, raw: str) -> dict[str, Any]:
        text = str(raw)
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            return {"steps": []}
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            # Try to salvage a steps array
            arr_start = text.find("[")
            arr_end = text.rfind("]")
            if arr_start != -1 and arr_end > arr_start:
                try:
                    steps = json.loads(text[arr_start : arr_end + 1])
                    return {"steps": steps}
                except json.JSONDecodeError:
                    pass
            return {"steps": []}