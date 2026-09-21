"""
ReAct Reasoning Engine - Think, Act, Observe loop with reflection.

Implements the ReAct pattern (Reasoning + Acting) with:
- Structured think/act/observe loop
- Tool calling via LLM function calling (with text fallback)
- Periodic self-reflection to correct course
- Streaming support
"""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from .interfaces import (
    ILLMProvider,
    IReasoningEngine,
    IReflector,
    IToolExecutor,
    ReasoningContext,
)
from .types import (
    ActionType,
    ReasoningConfig,
    ReasoningStep,
    ReasoningTrace,
    StepStatus,
)

SYSTEM_PROMPT = """You are Titan Agent, a powerful autonomous agent.
You solve tasks by interleaving reasoning (THINK) and tool use (ACT), then observing results (OBSERVE).

Available tools:
{tools}

Rules:
1. Think about the problem step by step before acting.
2. Use exactly one tool per ACT turn (unless the task is trivial).
3. After each tool result, reason about what it means and decide the next action.
4. Return your final answer with FINAL_ANSWER when the task is solved.
5. If a tool fails, try an alternative approach instead of repeating the same call.
6. Stay on task - ignore irrelevant results.

Respond in this JSON format:
{{"thought": "your reasoning", "action": "tool_name or 'final_answer'", "action_input": {{...args or the answer text}}}}
"""


class ReActEngine(IReasoningEngine):
    """Think-Act-Observe loop with optional reflection."""

    def __init__(
        self,
        llm: ILLMProvider,
        tools: IToolExecutor,
        reflector: IReflector | None = None,
        config: ReasoningConfig | None = None,
    ):
        self.llm = llm
        self.tools = tools
        self.reflector = reflector
        self.config = config or ReasoningConfig()
        self._context = ReasoningContext(
            config=self.config, llm=llm, tools=tools, reflector=reflector
        )
        self._message_history: list[dict[str, str]] = []

    # ---------- Public API ----------

    async def reason(
        self,
        task: str,
        config: ReasoningConfig | None = None,
        trace: ReasoningTrace | None = None,
    ) -> ReasoningTrace:
        if config:
            self.config = config
        self._context = ReasoningContext(
            config=self.config,
            llm=self.llm,
            tools=self.tools,
            reflector=self.reflector,
        )
        self._message_history = []

        trace = trace or ReasoningTrace(task=task)
        steps = [step async for step in self.stream_reason(task)]
        trace.steps = steps
        if steps:
            last = steps[-1]
            if last.status == StepStatus.COMPLETED and last.action_type == ActionType.DECIDE:
                trace.final_answer = last.content
        from datetime import datetime, timezone
        trace.completed_at = datetime.now(timezone.utc)
        return trace

    async def stream_reason(
        self,
        task: str,
        config: ReasoningConfig | None = None,
    ) -> AsyncGenerator[ReasoningStep, None]:
        if config:
            self.config = config
            self._context.config = config
        self._message_history = []

        # Seed the conversation
        self._message_history.append({"role": "system", "content": self._build_system_prompt()})
        self._message_history.append({"role": "user", "content": task})

        for step_no in range(1, self.config.max_steps + 1):
            self._context.increment_step()

            # Generate LLM turn
            think_step = ReasoningStep(
                step_number=step_no,
                action_type=ActionType.THINK,
                content="",
                status=StepStatus.IN_PROGRESS,
            )
            try:
                decision = await self._generate_decision()
            except Exception as exc:  # noqa: BLE001 - agent loop must survive any LLM error
                think_step.status = StepStatus.FAILED
                think_step.error = str(exc)
                yield think_step
                return

            think_step.content = decision.get("thought", "")
            think_step.status = StepStatus.COMPLETED
            yield think_step

            action = decision.get("action", "final_answer")
            action_input = decision.get("action_input") or {}

            # Final answer path
            if action in ("final_answer", "answer", ""):
                answer_step = ReasoningStep(
                    step_number=step_no,
                    action_type=ActionType.DECIDE,
                    content=action_input if isinstance(action_input, str) else json.dumps(action_input),
                    status=StepStatus.COMPLETED,
                )
                yield answer_step
                return

            # Tool execution path
            act_step = ReasoningStep(
                step_number=step_no,
                action_type=ActionType.ACT,
                content=f"{action}({json.dumps(action_input)[:500]})",
                tool_name=action,
                tool_args=action_input,
                status=StepStatus.IN_PROGRESS,
            )
            try:
                if not self.tools.has_tool(action):
                    raise LookupError(f"Unknown tool: {action}")
                result = await self.tools.execute(action, action_input)
                act_step.tool_result = self._truncate(str(result), self.config.max_observation_tokens)
                act_step.status = StepStatus.COMPLETED
            except Exception as exc:  # noqa: BLE001 - tool errors become observations
                act_step.tool_result = None
                act_step.error = str(exc)
                act_step.status = StepStatus.FAILED
            yield act_step

            # Observation feedback to the model
            observation = (
                f"Result of {action}: {act_step.tool_result}"
                if act_step.tool_result is not None
                else f"Error: {act_step.error}"
            )
            self._message_history.append(
                {"role": "user", "content": f"[OBSERVATION] {observation}"}
            )

            # Periodic reflection
            if self._context.should_reflect() and self._context.can_reflect():
                reflect_step = await self._reflect(step_no)
                yield reflect_step
                if reflect_step.metadata.get("halt"):
                    return

        # Max steps reached
        final_step = ReasoningStep(
            step_number=self.config.max_steps + 1,
            action_type=ActionType.DECIDE,
            content="Max steps reached without a final answer.",
            status=StepStatus.FAILED,
            error="Max steps exceeded",
        )
        yield final_step

    # ---------- Internals ----------

    def _build_system_prompt(self) -> str:
        tools_desc = "\n".join(
            f"- {t.get('name', 'unknown')}: {t.get('description', t.get('function', {}).get('description', ''))}"
            for t in (self.tools.get_available_tools() if self.tools else [])
        )
        return SYSTEM_PROMPT.format(tools=tools_desc or "(no tools available)")

    async def _generate_decision(self) -> dict[str, Any]:
        """Ask the LLM for the next thought/action decision."""
        # Prefer native tool calling
        if hasattr(self.llm, "complete_with_tools"):
            try:
                response = await self.llm.complete_with_tools(
                    messages=self._message_history,
                    tools=self.tools.get_available_tools() if self.tools else [],
                    temperature=self.config.temperature,
                    max_tokens=min(self.config.max_thinking_tokens, 4096),
                )
                self._message_history.append(
                    {"role": "assistant", "content": str(response)[:2000]}
                )
                return self._parse_tool_response(response)
            except NotImplementedError:
                pass

        # Text fallback: ask for structured JSON
        raw = await self.llm.complete(
            messages=self._message_history,
            temperature=self.config.temperature,
            max_tokens=min(self.config.max_thinking_tokens, 4096),
        )
        if isinstance(raw, AsyncGenerator):  # pragma: no cover - streamed fallback
            chunks = [chunk async for chunk in raw]
            raw = "".join(chunks)
        text = str(raw)
        self._message_history.append({"role": "assistant", "content": text[:2000]})
        return self._parse_text_decision(text)

    def _parse_tool_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse a native tool-calling response."""
        if isinstance(response, dict) and response.get("tool_calls"):
            call = response["tool_calls"][0]
            fn = call.get("function", {})
            name = fn.get("name", "final_answer")
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                args = {"text": fn.get("arguments", "")}
            return {"thought": response.get("content", ""), "action": name, "action_input": args}
        # Wrapped response {content, tool_calls}
        content = ""
        if isinstance(response, dict):
            content = str(response.get("content", ""))
            if response.get("message"):
                response = response["message"]
        return {"thought": content, "action": "final_answer", "action_input": content}

    def _parse_text_decision(self, text: str) -> dict[str, Any]:
        """Parse the model's structured JSON/text response."""
        cleaned = text.strip()
        # Try JSON extract
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
                return {
                    "thought": data.get("thought", ""),
                    "action": data.get("action", "final_answer"),
                    "action_input": data.get("action_input", {}),
                }
            except json.JSONDecodeError:
                pass
        # Fallback: whole text is the answer
        return {"thought": "", "action": "final_answer", "action_input": cleaned}

    async def _reflect(self, step_no: int) -> ReasoningStep:
        """Run a reflection turn."""
        step = ReasoningStep(
            step_number=step_no,
            action_type=ActionType.REFLECT,
            content="",
            status=StepStatus.PENDING,
        )
        if not self.reflector:
            step.status = StepStatus.SKIPPED
            return step
        self._context.increment_reflection()
        try:
            insights = await self.reflector.reflect(
                ReasoningTrace(task=self._message_history[1]["content"]) if len(self._message_history) > 1
                else ReasoningTrace(task=""),
            )
            step.content = str(insights.get("insight", insights))
            step.metadata["halt"] = bool(insights.get("halt", False))
            step.metadata["correction"] = insights.get("correction")
            step.status = StepStatus.COMPLETED
            if step.content:
                self._message_history.append(
                    {"role": "user", "content": f"[REFLECTION] {step.content}"}
                )
        except Exception as exc:  # noqa: BLE001 - reflection is best-effort
            step.error = str(exc)
            step.status = StepStatus.FAILED
        return step

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + f"...[truncated {len(text) - limit} chars]"