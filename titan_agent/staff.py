"""
Phase 9 — Dedicated Subagent Staff: named, specialised child agents.

Phase 7 gave Titan a generic SubagentPool (every child is the same agent).
Phase 9 gives each subagent a REAL ROLE: a persona overlay injected into its
system prompt, tuned run options (mode/effort/strategy) and an enforced tool
policy so a researcher cannot commit code and a reviewer cannot rewrite files.

How it works
------------
- :class:`Specialist` describes one role. :data:`SPECIALISTS` is the roster.
- :class:`ToolPolicy` filters which tools a role may see AND execute:
  ``allowed_tools=None`` means "everything except ``blocked_tools``";
  a non-None ``allowed_tools`` set means "only these".
- :class:`StaffPool` runs a named specialist via the headless runner. Each child
  gets a fresh session id (``sub-<parent>-<role>-<n>``) and a freshly built
  agent whose tool catalog and ``execute_tool_unified`` enforce the role
  policy. The persona is appended to the child's system prompt (``system_extra``).
- Parallelism is bounded by ``max_workers`` (default 2; Full Access raises it).
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import headless
from .subagents import SubagentResult


@dataclass(frozen=True)
class ToolPolicy:
    """Which tools a role may use. ``allowed`` of None = everything except blocked."""

    allowed: frozenset[str] | None = None
    blocked: frozenset[str] = frozenset()

    def allows(self, name: str) -> bool:
        if name in self.blocked:
            return False
        if self.allowed is None:
            return True
        return name in self.allowed

    def filter_definitions(self, defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop tool-schema entries the role may not use."""
        if self.allowed is None and not self.blocked:
            return list(defs)
        out = []
        for d in defs:
            fn = d.get("function", d)
            if self.allows(str(fn.get("name", ""))):
                out.append(d)
        return out


@dataclass(frozen=True)
class Specialist:
    """One named subagent role."""

    id: str
    title: str
    description: str          # when the parent agent should pick this role
    persona: str              # system-prompt overlay injected into the child
    mode: str = "fast"
    effort: str = "auto"
    strategy: str = "auto"
    allowed_tools: frozenset[str] | None = None
    blocked_tools: frozenset[str] = frozenset()


# Read-only-ish roles must stay hands-off: these tools never appear/execute.
_WRITE_TOOLS: frozenset[str] = frozenset({
    "write_file", "delete_file", "git_commit", "start_http_server",
    "stop_http_server", "take_screenshot",
})
_AGENT_SPAWNERS: frozenset[str] = frozenset({"subagent_delegate", "subagent_team", "subagent_roles"})
_TELEGRAM_WRITE: frozenset[str] = frozenset({"telegram_send", "telegram_login_confirm"})

_GENERALIST = Specialist(
    id="generalist",
    title="Generalist",
    description="Default worker — same behaviour as a plain subagent. Use when the sub-task needs no specialisation.",
    persona="",
)

SPECIALISTS: dict[str, Specialist] = {
    s.id: s
    for s in [
        _GENERALIST,
        Specialist(
            id="planner",
            title="Strategic Planner",
            description="Decomposes a big goal into an ordered, dependency-aware execution plan with verification checkpoints. Pick for 'make a plan for ...'.",
            persona=(
                "You are a STRATEGIC PLANNER. Your job is to decompose the requested goal\n"
                "into a clear, ordered execution plan: concrete steps, tool calls per step,\n"
                "dependencies, risks and a verification checkpoint per milestone. Write\n"
                "the plan as structured markdown. Do NOT execute the plan yourself —\n"
                "produce the plan."
            ),
            mode="fast",
            effort="high",
            strategy="plan",
        ),
        Specialist(
            id="researcher",
            title="Researcher",
            description="Searches the web, deep-searches topics and reads workspace files to gather verified facts with sources. Pick for 'research ...', 'find ...', 'what is ...'.",
            persona=(
                "You are a RESEARCHER. Gather verified facts and evidence for the question:\n"
                "search the web, deep-search, read files and RAG. Cite sources precisely\n"
                "(URLs / file paths). Never fabricate facts — if you cannot find evidence,\n"
                "say so explicitly. You are read-only: do not write, delete or commit files.\n"
                "Deliver a concise, source-backed research brief."
            ),
            mode="deep_search",
            effort="high",
            strategy="auto",
            blocked_tools=_WRITE_TOOLS | _AGENT_SPAWNERS,
        ),
        Specialist(
            id="coder",
            title="Coder",
            description="Implements, fixes and refactors code in the workspace using real tools (read/edit/run). Pick for 'implement ...', 'fix the bug in ...', 'write ...'.",
            persona=(
                "You are a CODER. Implement, fix or refactor the requested code using the\n"
                "workspace tools. Write clean, idiomatic code; run the relevant tests or\n"
                "commands to verify your changes; then git-commit if the workspace repo\n"
                "is cleanly usable. If something is ambiguous, choose the most reasonable\n"
                "interpretation and note it. Verify before reporting."
            ),
            mode="fast",
            effort="high",
            strategy="auto",
            blocked_tools=_TELEGRAM_WRITE,
        ),
        Specialist(
            id="reviewer",
            title="Critical Reviewer",
            description="Reviews code/results for bugs, edge cases, security and correctness — read-only critique with a verdict. Pick for 'review ...', 'check my code', 'is this correct?'.",
            persona=(
                "You are a CRITICAL REVIEWER. Analyse the given code/result for bugs,\n"
                "edge cases, security issues, performance and correctness. You are\n"
                "read-only: never write, delete or commit files. Produce a verdict\n"
                "(APPROVED / CHANGES REQUESTED / REJECTED) with a numbered list of\n"
                "specific, actionable findings."
            ),
            mode="fast",
            effort="high",
            strategy="react",
            allowed_tools=frozenset({
                "execute_command", "read_file", "list_files", "rag_search",
                "web_search", "git_status", "git_diff", "git_log",
                "memory_save", "memory_search", "vault_list",
            }),
        ),
        Specialist(
            id="tester",
            title="Verifier / Tester",
            description="Runs tests, executes commands and verifies claims/behaviour empirically. Pick for 'test ...', 'verify ...', 'does it pass?'.",
            persona=(
                "You are a VERIFIER / TESTER. Empirically validate the requested claim or\n"
                "change: run the tests and commands, inspect the output, and report a\n"
                "clear PASS / FAIL verdict per check with the exact commands you ran.\n"
                "Never assert success without executing it. You may not commit or send\n"
                "messages — verify only."
            ),
            mode="fast",
            effort="high",
            strategy="auto",
            blocked_tools=_WRITE_TOOLS | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
    ]
}

# Small aliases so the parent can write "code", "research", "plan", "review",
# "test" or "qa" and still land on the right specialist.
_ROLE_ALIASES: dict[str, str] = {
    "code": "coder",
    "coding": "coder",
    "developer": "coder",
    "engineer": "coder",
    "research": "researcher",
    "investigator": "researcher",
    "plan": "planner",
    "planning": "planner",
    "strategist": "planner",
    "review": "reviewer",
    "critic": "reviewer",
    "auditor": "reviewer",
    "test": "tester",
    "testing": "tester",
    "qa": "tester",
    "verifier": "tester",
}


def get_specialist(role: str | None) -> Specialist:
    """Resolve a role id or alias to a Specialist (unknown -> generalist)."""
    key = (role or "generalist").strip().lower()
    return SPECIALISTS.get(key) or SPECIALISTS.get(_ROLE_ALIASES.get(key, ""), _GENERALIST)


def staff_catalog() -> list[dict[str, str]]:
    """Machine-readable roster for the parent agent and the UI."""
    return [
        {
            "id": s.id,
            "title": s.title,
            "description": s.description,
        }
        for s in SPECIALISTS.values()
        if s.id != "generalist"
    ]


# --------------------------------------------------------------------------
# StaffPool
# --------------------------------------------------------------------------

SpecRunner = Callable[[Specialist, str, dict[str, Any]], tuple[int, str, list[dict[str, Any]]]]


def _build_specialist_agent(spec: Specialist):
    """Fresh agent for one role: filtered tool catalog + enforced tool policy."""
    policy = ToolPolicy(allowed=spec.allowed_tools, blocked=spec.blocked_tools)
    return headless.build_agent(tools=None, tool_policy=policy)


class StaffPool:
    """Runs named specialist subagents and collects their results."""

    def __init__(
        self,
        runner: SpecRunner | None = None,
        max_workers: int = 2,
    ):
        self.runner = runner or self._default_runner
        self.max_workers = max(1, int(max_workers))

    @staticmethod
    def _default_runner(
        spec: Specialist,
        task: str,
        opts: dict[str, Any],
    ) -> tuple[int, str, list[dict[str, Any]]]:
        agent = _build_specialist_agent(spec)
        return headless.run_headless(
            task,
            strategy=str(opts.get("strategy") or spec.strategy),
            mode=str(opts.get("mode") or spec.mode),
            effort=str(opts.get("effort") or spec.effort),
            session_id=str(opts.get("session_id", "staff")),
            agent=agent,
            system_extra=spec.persona,
        )

    async def run(
        self,
        role: str | None,
        task: str,
        session_id: str = "default_session",
        label: str | None = None,
        opts: dict[str, Any] | None = None,
    ) -> SubagentResult:
        """Run one task with the named specialist (blocking until done)."""
        spec = get_specialist(role)
        o: dict[str, Any] = dict(opts or {})
        o.setdefault("session_id", f"sub-{session_id}-{label or spec.id}")
        try:
            code, final, events = await asyncio.to_thread(self.runner, spec, task, o)
        except Exception as exc:  # noqa: BLE001 - report, don't crash the parent
            return SubagentResult(label=label or spec.id, exit_code=1, final="", error=f"{exc}")
        return SubagentResult(label=label or spec.id, exit_code=code, final=final, events=events)

    async def team(
        self,
        tasks: list[str],
        roles: list[str] | None = None,
        session_id: str = "default_session",
        labels: list[str] | None = None,
        opts: dict[str, Any] | None = None,
    ) -> list[SubagentResult]:
        """Run several tasks in parallel, each with its own (or generalist) role."""
        if not tasks:
            return []
        roles = roles or []
        if len(roles) < len(tasks):
            roles = roles + ["generalist"] * (len(tasks) - len(roles))
        labels = labels or [f"worker-{i}" for i in range(1, len(tasks) + 1)]
        if len(labels) < len(tasks):
            labels = labels + [f"worker-{i}" for i in range(len(labels) + 1, len(tasks) + 1)]

        sem = asyncio.Semaphore(self.max_workers)

        async def one(task: str, role: str, label: str):
            async with sem:
                return await self.run(role, task, session_id=session_id, label=label, opts=opts)

        return await asyncio.gather(*(one(t, r, l) for t, r, l in zip(tasks, roles, labels)))