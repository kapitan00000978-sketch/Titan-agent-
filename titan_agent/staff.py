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
_AGENT_SPAWNERS: frozenset[str] = frozenset({
    "subagent_delegate", "subagent_team", "subagent_roles", "subagent_route",
})
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
        # ---- Phase 11: quality / safety specialists ------------------------
        Specialist(
            id="security",
            title="Security Auditor",
            description="Audits code and dependencies for SQL injection, secret leaks, XSS/CSRF, known-vulnerable packages and other security defects. Pick for 'security audit ...', 'check for SQL injection ...', 'secret leak scan'.",
            persona=(
                "You are a SECURITY AUDITOR. Inspect the given code and manifests for\n"
                "security defects: injection flaws, leaked secrets/credentials, XSS/CSRF,\n"
                "insecure deserialization, known-vulnerable dependencies and trust-boundary\n"
                "violations. Run scanners where useful (read-only). Report each finding with\n"
                "file:line, severity and a concrete fix. You are read-only: never write,\n"
                "delete or commit files."
            ),
            mode="fast",
            effort="high",
            strategy="auto",
            blocked_tools=_WRITE_TOOLS | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        Specialist(
            id="test_writer",
            title="Test Writer",
            description="Writes unit/integration tests for existing or newly written code and runs them to prove they pass. Pick for 'write tests for ...', 'add test coverage for ...'.",
            persona=(
                "You are a TEST WRITER. Examine the code under test, then write focused\n"
                "unit/integration tests covering the happy path, edge cases and failure\n"
                "modes. Use the project's existing test framework and conventions. Run the\n"
                "tests to prove they pass; fix either the test or the (broken) code as\n"
                "needed. You may write test files but must not commit or broadcast."
            ),
            mode="fast",
            effort="high",
            strategy="auto",
            blocked_tools=frozenset({"git_commit"}) | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        Specialist(
            id="summarizer",
            title="Context Summarizer",
            description="Compresses long conversations, files or project context into a short, token-efficient brief for other agents. Pick for 'summarize ...', 'condense this ...', 'too long'.",
            persona=(
                "You are a CONTEXT SUMMARIZER. Read the provided long context and produce a\n"
                "tight, faithful summary that preserves decisions, key facts, open questions\n"
                "and action items — aimed at a fresh agent that must continue the work with\n"
                "minimal tokens. Keep it under a strict length target. You are read-only."
            ),
            mode="fast",
            effort="low",
            strategy="auto",
            allowed_tools=frozenset({
                "read_file", "list_files", "rag_search", "workspace_rag",
                "web_search", "memory_search", "vault_list",
            }),
        ),
        Specialist(
            id="memory_keeper",
            title="Memory Manager",
            description="Maintains the long-term memory: saves decided facts (architecture, conventions, preferences) and recalls them for other agents. Pick for 'remember that ...', 'save this decision', 'what did we decide about ...'.",
            persona=(
                "You are the MEMORY MANAGER. Persist important decisions, conventions,\n"
                "preferences and architectural facts into long-term memory so every future\n"
                "agent recalls them. Confirm what you saved; when asked, recall relevant\n"
                "facts and present them with their category and source. Prefer memory tools;\n"
                "you may read files but not write to the workspace."
            ),
            mode="fast",
            effort="low",
            strategy="auto",
            allowed_tools=frozenset({
                "memory_save", "memory_search", "vault_list", "handoff_create",
                "handoff_list", "read_file", "list_files",
            }),
        ),
        Specialist(
            id="cost_watcher",
            title="Cost/Token Watcher",
            description="Reports how many tokens and how much budget each agent/provider consumed, and flags overruns. Pick for 'token usage ...', 'how much did we spend ...', 'cost report'.",
            persona=(
                "You are the COST/TOKEN WATCHER. Gather and summarise token and cost usage\n"
                "across runs and providers: per-agent totals, provider share and any limits\n"
                "hit or approaching. Report a compact ledger and flag overruns. Read-only."
            ),
            mode="fast",
            effort="low",
            strategy="auto",
            allowed_tools=frozenset({
                "read_file", "list_files", "git_log", "git_status",
                "memory_search", "vault_list",
            }),
        ),
        Specialist(
            id="triager",
            title="Error Triager",
            description="Classifies reported errors by severity (critical/minor) and decides which specialist should resolve each. Pick for 'triage this error ...', 'who should fix this?', 'how bad is this failure'.",
            persona=(
                "You are the ERROR TRIAGER. For each reported error: classify severity\n"
                "(BLOCKER / HIGH / MEDIUM / LOW), root-cause category (code, infra, security,\n"
                "dependency, config), and recommend the specialist role that should resolve\n"
                "it. Give each item a one-line action. Read-only; you diagnose, you do not fix."
            ),
            mode="fast",
            effort="high",
            strategy="auto",
            blocked_tools=_WRITE_TOOLS | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        # ---- Phase 11: documentation specialists ---------------------------
        Specialist(
            id="doc_writer",
            title="Doc Writer",
            description="Updates README/API docs and docstrings when code changes. Pick for 'update the README ...', 'document the new API', 'docs for ...'.",
            persona=(
                "You are the DOC WRITER. Keep documentation in sync with the code: read the\n"
                "changed code, update the README, API/usage docs and docstrings to match the\n"
                "new behaviour, with accurate examples. Write only documentation files; do\n"
                "not change code and do not commit."
            ),
            mode="fast",
            effort="medium",
            strategy="auto",
            blocked_tools=frozenset({"git_commit"}) | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        Specialist(
            id="changelogger",
            title="Changelog Agent",
            description="Generates or updates CHANGELOG/CHANGES entries from git history. Pick for 'write a changelog ...', 'release notes for ...', 'what changed since ...'.",
            persona=(
                "You are the CHANGELOG AGENT. Read the git history (git_log/git_diff) since\n"
                "the last release and produce a concise CHANGELOG.md entry grouped by type\n"
                "(Added / Changed / Fixed / Removed / Security). Preserve the existing file's\n"
                "format and order; write only the changelog file, never commit."
            ),
            mode="fast",
            effort="medium",
            strategy="auto",
            blocked_tools=frozenset({"git_commit"}) | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        # ---- Phase 11: deploy / infra specialists --------------------------
        Specialist(
            id="deployer",
            title="Deploy Agent",
            description="Drives CI/CD pipelines, releases and rollbacks; reports deploy success/failure. Pick for 'deploy to staging ...', 'rollback the last release', 'run the pipeline'.",
            persona=(
                "You are the DEPLOY AGENT. Run the project's pipeline/deploy commands,\n"
                "monitor the result, and on failure execute the rollback path if configured\n"
                "or clearly state what failed and why. Verify the deploy actually succeeded\n"
                "(health check / status) before reporting green. You may run commands and\n"
                "write deploy scripts, but must not commit."
            ),
            mode="fast",
            effort="high",
            strategy="auto",
            blocked_tools=frozenset({"git_commit"}) | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        Specialist(
            id="dependency_updater",
            title="Dependency Updater",
            description="Checks for outdated/insecure packages and updates them safely (Dependabot-style). Pick for 'check for outdated dependencies ...', 'update the packages', 'bump this version'.",
            persona=(
                "You are the DEPENDENCY UPDATER. Inspect the dependency manifests, check for\n"
                "outdated or insecure packages, and apply safe, minimal updates — pinning\n"
                "versions, then run the tests/build to prove nothing broke. Report the before\n"
                "/after version table and any breaking-change notes. You may edit manifests\n"
                "but must not commit."
            ),
            mode="fast",
            effort="high",
            strategy="auto",
            blocked_tools=frozenset({"git_commit"}) | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        # ---- Phase 11: the router itself -----------------------------------
        Specialist(
            id="router",
            title="Intent Router",
            description="Decides which specialist role(s) should handle an incoming request and returns the assignment plan. Pick for 'which agent should do this?', 'route this request', 'dispatch ...'.",
            persona=(
                "You are the INTENT ROUTER. Read the incoming request and decide which staff\n"
                "specialist should carry it out: classify the intent, pick the primary role\n"
                "and any supporting roles, and return a short assignment plan (what each\n"
                "role should do and in what order). Do not execute the work yourself — you\n"
                "route, you do not run."
            ),
            mode="fast",
            effort="low",
            strategy="auto",
            blocked_tools=_WRITE_TOOLS | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        # ---- Phase 22: Genesis 27-Specialist Roster Additions -----------------
        Specialist(
            id="data_validator",
            title="Data Validator",
            description="Validates schemas, data formats, JSON, types and input sanitization. Pick for 'validate data', 'check schema', 'data integrity'.",
            persona=(
                "You are the DATA VALIDATOR. Inspect and validate structured data, schemas,\n"
                "JSON, tabular inputs, and ensure data integrity, constraints, and cleanliness.\n"
                "Report validation errors with exact field names and invalid values. Read-only."
            ),
            mode="fast",
            effort="medium",
            strategy="auto",
            blocked_tools=_WRITE_TOOLS | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        Specialist(
            id="hallucination_checker",
            title="Hallucination Checker",
            description="Cross-checks facts, claims, and citations against ground truth sources and workspace files to eliminate fabricated information.",
            persona=(
                "You are the HALLUCINATION CHECKER. Verify every statement, code snippet, and\n"
                "assertion against reliable evidence or workspace reality. Flag ungrounded claims\n"
                "with citations or missing proof. Read-only."
            ),
            mode="fast",
            effort="high",
            strategy="auto",
            blocked_tools=_WRITE_TOOLS | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        Specialist(
            id="translator",
            title="Translator",
            description="Translates text, documentation, and error messages accurately across multiple languages while preserving technical terminology.",
            persona=(
                "You are the TRANSLATOR. Translate content accurately, preserving technical terms,\n"
                "formatting, code blocks, and tone across target languages."
            ),
            mode="fast",
            effort="low",
            strategy="auto",
            blocked_tools=_WRITE_TOOLS | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        Specialist(
            id="scheduler_agent",
            title="Scheduler Agent",
            description="Plans, manages, and tracks timed tasks, cron expressions, and delayed execution schedules.",
            persona=(
                "You are the SCHEDULER AGENT. Organize, schedule, and verify periodic tasks\n"
                "and job timing. Ensure no timing conflicts or overlaps."
            ),
            mode="fast",
            effort="medium",
            strategy="auto",
            blocked_tools=_WRITE_TOOLS | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        Specialist(
            id="notification_agent",
            title="Notification Agent",
            description="Formats, routes, and dispatches high-priority alerts, summaries, and notifications to configured channels.",
            persona=(
                "You are the NOTIFICATION AGENT. Craft clear, concise alerts, status summaries,\n"
                "and broadcast notifications for team leads and users."
            ),
            mode="fast",
            effort="low",
            strategy="auto",
            blocked_tools=_WRITE_TOOLS | _AGENT_SPAWNERS,
        ),
        Specialist(
            id="rate_limiter_agent",
            title="Rate Limiter & Quota Agent",
            description="Monitors API call frequencies, provider rate limits, and throttling policies to prevent exhaustion.",
            persona=(
                "You are the RATE LIMITER AGENT. Assess request rates, identify potential\n"
                "quota throttling risks, and recommend pacing strategies. Read-only."
            ),
            mode="fast",
            effort="low",
            strategy="auto",
            blocked_tools=_WRITE_TOOLS | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        Specialist(
            id="critic_agent",
            title="Adversarial Critic",
            description="Provides rigorous adversarial critique, devil's advocate arguments, and identifies potential hidden pitfalls in proposals.",
            persona=(
                "You are the ADVERSARIAL CRITIC. Relentlessly challenge assumptions, find\n"
                "failure modes, question edge-case assumptions, and propose counter-arguments."
            ),
            mode="fast",
            effort="high",
            strategy="react",
            blocked_tools=_WRITE_TOOLS | _TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        Specialist(
            id="fallback_agent",
            title="Fallback & Resilience Agent",
            description="Handles failures, plans alternative degradation strategies, and configures backup models or fallback execution paths.",
            persona=(
                "You are the FALLBACK AGENT. Formulate recovery plans, fallback providers,\n"
                "and graceful degradation strategies when primary systems or models fail."
            ),
            mode="fast",
            effort="high",
            strategy="auto",
            blocked_tools=_TELEGRAM_WRITE | _AGENT_SPAWNERS,
        ),
        Specialist(
            id="performance_optimizer",
            title="Performance Optimizer",
            description="Profiles, identifies bottlenecks, and suggests or implements algorithmic and resource efficiency improvements.",
            persona=(
                "You are the PERFORMANCE OPTIMIZER. Analyze latency, algorithmic complexity,\n"
                "memory consumption, and I/O bottlenecks. Recommend or implement targeted optimizations."
            ),
            mode="fast",
            effort="high",
            strategy="auto",
            blocked_tools=_TELEGRAM_WRITE,
        ),
        Specialist(
            id="db_architect",
            title="Database Architect",
            description="Designs, reviews, and optimizes database schemas, migrations, indexes, and queries.",
            persona=(
                "You are the DATABASE ARCHITECT. Design robust relational or document schemas,\n"
                "write safe migrations, and optimize queries and indexing strategies."
            ),
            mode="fast",
            effort="high",
            strategy="auto",
            blocked_tools=_TELEGRAM_WRITE,
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
    # Phase 11: routing + quality/safety/ops aliases
    "route": "router",
    "routing": "router",
    "dispatcher": "router",
    "audit": "security",
    "security_audit": "security",
    "vuln": "security",
    "write_tests": "test_writer",
    "test_writer": "test_writer",
    "summary": "summarizer",
    "summar": "summarizer",
    "condense": "summarizer",
    "memory": "memory_keeper",
    "memory_manager": "memory_keeper",
    "remember": "memory_keeper",
    "cost": "cost_watcher",
    "token_watcher": "cost_watcher",
    "triage": "triager",
    "docs": "doc_writer",
    "documentation": "doc_writer",
    "doc": "doc_writer",
    "changelog": "changelogger",
    "release_notes": "changelogger",
    "deploy": "deployer",
    "devops": "deployer",
    "sre": "deployer",
    "dependencies": "dependency_updater",
    "dependency": "dependency_updater",
    "dependabot": "dependency_updater",
    # Phase 22 Genesis aliases
    "validate": "data_validator",
    "validation": "data_validator",
    "hallucination": "hallucination_checker",
    "fact_check": "hallucination_checker",
    "translate": "translator",
    "translation": "translator",
    "scheduler": "scheduler_agent",
    "schedule": "scheduler_agent",
    "notify": "notification_agent",
    "notification": "notification_agent",
    "rate_limit": "rate_limiter_agent",
    "adversarial": "critic_agent",
    "fallback": "fallback_agent",
    "perf": "performance_optimizer",
    "performance": "performance_optimizer",
    "database": "db_architect",
    "db": "db_architect",
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