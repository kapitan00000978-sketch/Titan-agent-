"""
Phase 3 — Live-loop integration of the Phase 2 core engines.

Bridges the production ``LLMClient`` and the live tool executor onto the core
``ILLMProvider`` / ``IToolExecutor`` interfaces, then runs structured reasoning
strategies (plan / react / tot) inside the real agent loop with guardrails.

Strategies produced by :class:`StructuredEngine`:

- ``plan``  - PlanExecutor builds a step plan first, then ReAct executes it
- ``react`` - pure structured ReAct (think -> act -> observe + reflection)
- ``tot``   - Tree-of-Thoughts explores candidate strategies first, then ReAct
              executes the winning path with real tools

Guardrails: every tool activation is evaluated by a PolicyEngine (default
``DEFAULT_RULES``); deny / require-approval decisions are enforced before the
underlying tool runs, with optional human-in-the-loop approval waiting.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

from . import config as _cfg
from .agent import AgentEvent
from .core.guardrails.hitl import ApprovalStatus, HumanInTheLoop
from .core.guardrails.policy import DEFAULT_RULES, Decision, PolicyEngine
from .core.reasoning.debate import DebateEngine
from .core.reasoning.interfaces import ILLMProvider, IReflector, IToolExecutor
from .core.reasoning.planner import PlanExecutor
from .core.reasoning.react import ReActEngine
from .core.reasoning.reflexion import ReflexionEngine
from .core.reasoning.tot import LLMEvaluator, ToTEngine
from .core.reasoning.types import (
    ActionType,
    ReasoningConfig,
    ReasoningStep,
    ReasoningTrace,
    StepStatus,
)
from .llm_client import LLMClient

log = logging.getLogger(__name__)

# Valid run_task strategies ("auto" keeps the classic loop untouched).
VALID_STRATEGIES = ("auto", "plan", "react", "tot", "reflexion", "debate")


# --------------------------------------------------------------------------
# LLM bridge
# --------------------------------------------------------------------------

class LLMBridge(ILLMProvider):
    """Adapter: production LLMClient -> core ILLMProvider."""

    def __init__(self, client: LLMClient):
        self.client = client

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> Any:
        resp = await self.client.chat_completion(
            messages, tools=None, temperature=temperature, max_tokens=max_tokens
        )
        if stream:

            async def _gen():  # pragma: no cover - direct str is the common path
                yield resp.content

            return _gen()
        return resp.content

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        resp = await self.client.chat_completion(
            messages, tools=tools, temperature=temperature, max_tokens=max_tokens
        )
        return {"content": resp.content, "tool_calls": resp.tool_calls, "thoughts": resp.thoughts}


# --------------------------------------------------------------------------
# Tool bridge with policy guardrails
# --------------------------------------------------------------------------

def _resource_for(tool_name: str, args: Any) -> str:
    """Derive the policy resource for a tool activation (command text, path,
    url...) so rules like `execute_command / rm -rf` match by prefix."""
    if isinstance(args, dict):
        for key in ("command", "path", "url", "target", "resource", "delete", "query"):
            value = args.get(key)
            if isinstance(value, str) and value:
                return value
    try:
        return json.dumps(args, default=str)[:2000]
    except (TypeError, ValueError):
        return str(args)[:2000]


class ToolBridge(IToolExecutor):
    """Adapter: live tool executor + PolicyEngine guardrail gate."""

    def __init__(
        self,
        execute_fn: Callable[[str, dict[str, Any]], Awaitable[str]],
        get_tools_fn: Callable[[], list[dict[str, Any]]],
        policy_engine: PolicyEngine | None = None,
        hitl: HumanInTheLoop | None = None,
        hitl_timeout: float = 60.0,
        auto_approve: bool | None = None,
        defer_approval: bool = False,
    ):
        self.execute_fn = execute_fn
        self.get_tools_fn = get_tools_fn
        self.policy = policy_engine if policy_engine is not None else PolicyEngine(list(DEFAULT_RULES))
        self.hitl = hitl
        self.hitl_timeout = hitl_timeout
        # Phase 8: in FULL/ABSOLUTE access every approval gate is auto-granted
        # (None = derive from config so a runtime toggle applies immediately).
        self.auto_approve = _cfg.full_access_enabled() if auto_approve is None else auto_approve
        # Phase 14: when True and no HITL is attached, require-approval tools are
        # handed through to the underlying executor (ToolRegistry) instead of being
        # denied here — the live agent wires HITL at the registry layer so every
        # execution path shares ONE approval gate (no double approval prompts).
        self.defer_approval = defer_approval

    async def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        if self.policy is not None:
            access = (
                PolicyEngine.ACCESS_ABSOLUTE
                if _cfg.absolute_access_enabled()
                else (PolicyEngine.ACCESS_FULL if _cfg.full_access_enabled() else PolicyEngine.ACCESS_NORMAL)
            )
            decision = self.policy.check(tool_name, _resource_for(tool_name, args), access=access)
            if decision.decision == Decision.DENY:
                why = "; ".join(decision.reasons) or "denied by policy"
                return f"Error: blocked by safety policy ({why})."
            if (
                decision.decision == Decision.REQUIRE_APPROVAL
                and not await self._approve(tool_name, args, decision)
            ):
                why = "; ".join(decision.reasons) or "requires human approval"
                return f"Error: approval required but not granted ({why})."
        return await self.execute_fn(tool_name, args or {})

    async def _approve(self, tool_name: str, args: dict[str, Any], check_result) -> bool:
        if self.auto_approve:
            return True
        if self.hitl is None:
            # Phase 14: defer_approval=True lets the request through so the
            # execution layer (ToolRegistry HITL gate) handles it — otherwise
            # we keep the classic "no responder" denial.
            return self.defer_approval
        try:
            req = self.hitl.request(
                tool_name,
                _resource_for(tool_name, args),
                details={"args": args},
                reason="; ".join(check_result.reasons or []),
            )
            req = await self.hitl.wait(req, timeout=self.hitl_timeout)
            return req.status == ApprovalStatus.APPROVED
        except Exception as exc:  # noqa: BLE001 - approval is best-effort
            log.debug("Approval flow failed: %s", exc)
            return False

    def get_available_tools(self) -> list[dict[str, Any]]:
        """Return the tool list with a top-level 'name' (core prompt helpers
        rely on it; the LLM API shape `{type,function}` is preserved)."""
        out: list[dict[str, Any]] = []
        for tool in self.get_tools_fn():
            fn = tool.get("function") or {}
            if "name" not in tool:
                tool = {**tool, "name": fn.get("name", "")}
            out.append(tool)
        return out

    def has_tool(self, name: str) -> bool:
        return any(t.get("name") == name for t in self.get_available_tools())


# --------------------------------------------------------------------------
# Reflection bridge
# --------------------------------------------------------------------------

REFLECT_JSON_PROMPT = """You are the CRITIC phase of Titan Agent. Review the reasoning performed so far for the task.

Task: {task}

Recent reasoning states:
{states}

Critically evaluate: Is the approach on track? Are all claims verified by tool results?
Is anything missing or wrong? If the goal is already fully reached, set halt=true.
Respond with ONLY JSON: {{"insight": "...", "correction": "...", "halt": true|false}}
"""


class ReflectorAdapter(IReflector):
    """Adapter: LLM-based self-correction on the live loop's model."""

    def __init__(self, client: LLMClient, max_chars: int = 4000):
        self.client = client
        self.max_chars = max_chars

    async def reflect(
        self,
        trace: ReasoningTrace,
        focus: str | None = None,
    ) -> dict[str, Any]:
        states = "\n".join(
            f"[{s.action_type.value}] {(s.content or '')[:200]}" for s in trace.steps[-8:]
        )
        prompt = REFLECT_JSON_PROMPT.format(
            task=(focus or trace.task or "")[:1500], states=states[: self.max_chars]
        )
        try:
            raw = await self.client.chat_completion(
                [{"role": "user", "content": prompt}], temperature=0.2, max_tokens=600
            )
            data = _extract_json_dict(raw.content)
            return {
                "insight": data.get("insight", ""),
                "correction": data.get("correction"),
                "halt": bool(data.get("halt", False)),
            }
        except Exception as exc:  # noqa: BLE001 - reflection must never kill the loop
            return {"insight": "", "correction": None, "halt": False, "error": str(exc)}

    async def should_continue(self, trace: ReasoningTrace) -> tuple[bool, str]:
        return (True, "")


# --------------------------------------------------------------------------
# Structured engine
# --------------------------------------------------------------------------

class StructuredEngine:
    """Runs core reasoning strategies inside the live agent event stream."""

    def __init__(
        self,
        llm: LLMClient,
        execute_tool: Callable[[str, dict[str, Any]], Awaitable[str]],
        get_tools: Callable[[], list[dict[str, Any]]],
        session_id: str = "default_session",
        policy_engine: PolicyEngine | None = None,
        hitl: HumanInTheLoop | None = None,
        hitl_timeout: float = 30.0,
        auto_approve: bool = False,
        defer_approval: bool = False,
    ):
        self.llm_bridge = LLMBridge(llm)
        self.tool_bridge = ToolBridge(
            execute_tool,
            get_tools,
            policy_engine=policy_engine,
            hitl=hitl,
            hitl_timeout=hitl_timeout,
            auto_approve=auto_approve,
            defer_approval=defer_approval,
        )
        self.policy = self.tool_bridge.policy
        self.session_id = session_id

    # ---------- Public API ----------

    async def run(
        self,
        task: str,
        context: str | None = None,
        strategy: str = "react",
        max_steps: int = 15,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Execute a task with the requested strategy, yielding AgentEvents.

        ``context`` is extra system context (agent identity, tool catalog,
        remembered facts) prepended to the task for the reasoning engines.
        """
        strategy = strategy if strategy in ("plan", "react", "tot") else "react"
        cfg = self._build_config(max_steps, strategy)

        # --- 1) Strategy / planning phase ---
        seed = ""
        if strategy == "plan":
            yield AgentEvent("status", "Building a structured execution plan...")
            engine = PlanExecutor(self.llm_bridge, self.tool_bridge, cfg)
            plan = await engine.create_plan(
                task, available_tools=self.tool_bridge.get_available_tools()
            )
            yield AgentEvent(
                "plan",
                {
                    "goal": plan.goal,
                    "steps": [s.model_dump() for s in plan.steps],
                    "count": len(plan.steps),
                },
            )
            if plan.steps:
                steps_txt = "\n".join(
                    f"{i + 1}. {s.description}" for i, s in enumerate(plan.steps)
                )
                seed = "### EXECUTION PLAN (follow it; adapt when new information appears):\n" + steps_txt
                yield AgentEvent("status", f"Structured plan ready: {len(plan.steps)} steps.")
            else:
                yield AgentEvent("status", "Plan generator returned no steps - proceeding ReAct.")
        elif strategy == "tot":
            yield AgentEvent("status", "Tree-of-Thoughts: exploring candidate strategies...")
            engine = ToTEngine(self.llm_bridge, LLMEvaluator(self.llm_bridge), cfg)
            trace = await engine.reason(task)
            path = "\n".join(
                s.content
                for s in trace.steps
                if s.action_type in (ActionType.THINK, ActionType.PLAN) and s.content
            )
            if path:
                seed = "### STRATEGY (Tree-of-Thoughts best path - follow, adapt with tool results):\n" + path[:3000]
                yield AgentEvent("status", "ToT strategy ready - executing with tools.")
            else:
                yield AgentEvent("status", "ToT found no distinct path - proceeding ReAct.")
        elif strategy == "reflexion":
            yield AgentEvent("status", "Reflexion Loop: executing with self-critique & iterative refinement...")
            reflex_engine = ReflexionEngine(self.llm_bridge)
            res = await reflex_engine.run(task, max_cycles=3)
            for c in res.cycles:
                yield AgentEvent("thought", f"[Cycle {c.cycle}] Score: {c.score}/10 | Verdict: {c.verdict}\nCritique: {c.critique}")
            yield AgentEvent("status", f"Reflexion completed in {res.total_cycles} cycles (Improved: {res.improved}).")
            yield AgentEvent("final_answer", res.final_output)
            return
        elif strategy == "debate":
            yield AgentEvent("status", "Multi-Agent Debate: Advocate vs Skeptic with Judicial Arbitration...")
            debate_engine = DebateEngine(self.llm_bridge)
            res_d = await debate_engine.run_debate(task, rounds=2)
            for t in res_d.turns:
                yield AgentEvent("thought", f"[{t.speaker.upper()} (R{t.round_num})]\n{t.argument[:300]}...")
            yield AgentEvent("status", f"Debate concluded. Winner: {res_d.winner}")
            yield AgentEvent("final_answer", res_d.summary())
            return
        else:
            yield AgentEvent("status", "Structured ReAct engaged (think -> act -> observe).")

        # --- 2) Execution phase: ReAct with reflection + guardrails ---
        user_msg = "\n\n".join(
            p for p in (context or "", seed or "", f"USER TASK:\n{task}") if p
        )
        engine = ReActEngine(
            self.llm_bridge,
            self.tool_bridge,
            reflector=ReflectorAdapter(self.llm_bridge.client),
            config=cfg,
        )

        async for step in engine.stream_reason(user_msg, cfg):
            if step.action_type == ActionType.THINK and step.status == StepStatus.FAILED:
                yield AgentEvent("error", step.error or "LLM reasoning error.")
                return
            if step.action_type == ActionType.ACT:
                # Emit the call (with args) then the observed result, so the UI
                # sees the same shape as the classic loop's streaming events.
                yield AgentEvent("tool_call", {"name": step.tool_name, "arguments": step.tool_args or {}})
                yield AgentEvent(
                    "tool_result",
                    {
                        "name": step.tool_name,
                        "result": str(step.tool_result if step.tool_result is not None else (step.error or "no result")),
                        "status": step.status.value,
                    },
                )
                continue
            event = self._step_to_event(step)
            if event is not None:
                yield event
            if step.action_type == ActionType.DECIDE and step.status == StepStatus.COMPLETED:
                yield AgentEvent("final_answer", step.content)
                return
            if step.metadata.get("halt"):
                yield AgentEvent("status", "Reflection determined the goal is reached.")
                return

        yield AgentEvent("error", "Structured reasoning finished without a final answer.")

    # ---------- Internals ----------

    def _build_config(self, max_steps: int, strategy: str) -> ReasoningConfig:
        # Phase 8: FULL access lifts the 30-step structured-reasoning clamp so
        # deep strategy runs also keep working until the task is done.
        clamp = 1000 if _cfg.full_access_enabled() else 30
        cfg = ReasoningConfig(max_steps=max(3, min(int(max_steps), clamp)))
        if strategy in ("plan", "tot"):
            cfg.max_plan_steps = 8
        if strategy == "tot":
            cfg.tot_max_depth = 2
            cfg.tot_branching_factor = 3
        return cfg

    def _step_to_event(self, step: ReasoningStep) -> AgentEvent | None:
        if step.action_type == ActionType.THINK and step.content:
            return AgentEvent("thought", step.content)
        if step.action_type == ActionType.ACT:
            return AgentEvent(
                "tool_result",
                {
                    "name": step.tool_name,
                    "result": str(step.tool_result if step.tool_result is not None else (step.error or "no result")),
                    "status": step.status.value,
                },
            )
        if step.action_type == ActionType.REFLECT and step.content:
            return AgentEvent("status", f"[reflection] {step.content}")
        if step.action_type == ActionType.PLAN and step.content:
            return AgentEvent("status", f"[plan] {step.content}")
        return None


def _extract_json_dict(text: str) -> dict[str, Any]:
    s = str(text).strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        return {}
    try:
        data = json.loads(s[start : end + 1])
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}