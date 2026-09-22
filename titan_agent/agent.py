import asyncio
import json
import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import aiohttp

from .checkpoint import MAX_MESSAGES as CHECKPOINT_MAX_MESSAGES
from .checkpoint import CheckpointStore, RunCheckpoint
from .config import (
    CONTEXT_BUDGET_CHARS,
    DEEP_MAX_STEPS_BASE,
    LLM_TRANSIENT_RETRIES,
    MAX_ITERATIONS,
    MAX_STEPS_CAP,
    UNLIMITED_STEPS,
    WORKSPACE_DIR,
    full_access_enabled,
)
from .core.guardrails.hitl import ApprovalStatus, HumanInTheLoop
from .core.guardrails.policy import Decision, PolicyEngine
from .core.memory.memory_system import MemorySystem
from .core.memory.types import MemoryKind
from .gitops import auto_commit as git_auto_commit
from .gitops import git_commit, git_diff, git_status
from .llm_client import LLMClient
from .mcp_client import MCPManager
from .memory import MemoryManager
from .skills import SkillRegistry
from .telegram import TelegramError, TelegramManager
from .tools import ToolRegistry

log = logging.getLogger(__name__)

TITAN_SYSTEM_PROMPT = """You are TITAN AGENT — an ultra-powerful autonomous AI reasoning and execution engine, engineered to outperform classic agents (including Hermes-class and frontier-tier models) on real-world task completion.

### CORE PRINCIPLES (Plan-Act-Verify-Report + Reflect):
1. PLAN first, always: Before using any tool, briefly outline your strategy inside <thought> tags. Choose the smallest set of tool calls that fully completes the task.
2. ACT decisively: Use tools exactly as documented. Batch independent tool calls together in one turn when possible. Prefer concrete commands over speculation.
3. VERIFY results: After every tool result, check for errors. If a command fails, read the stderr, fix your arguments or approach, and retry with an alternative method — never give up on the first error.
4. REFLECT before reporting: You will get a chance to critically review your own work (critic phase) before the final answer — use it to catch missed requirements, unverified claims and errors.
5. REPORT clearly: End with a complete, well-structured final answer in markdown, in the user's language. Only claim something is done if you have actually verified it via tools.

### TOOL CATALOG (use these; the full live catalog is appended to your context):
- execute_command — run PowerShell/terminal commands (real OS execution)
- read_file / write_file / edit_file / list_directory — filesystem operations inside the workspace
- workspace_rag — local BM25 retrieval: finds the most relevant snippets (with file paths) across ALL workspace files for any question
- web_search — live DuckDuckGo internet search
- scrape_webpage — fetch readable text from a URL
- python_eval — run Python in an isolated subprocess
- deep_search — multi-hop, multi-source research dossier on a topic
- deep_coder — full software engineering cycle: write files, syntax-check, run tests
- launch_application — open Windows desktop apps
- system_info — read live OS / CPU / RAM / disk / Python environment facts
- manage_processes — list or kill running OS processes
- memory_save — store a fact in long-term persistent memory (remembered forever across sessions)
- memory_search — recall previously saved facts from long-term memory
- vault_list — browse the Memory Vault (scoped facts: global/project/team/user)
- handoff_create / handoff_list / handoff_resolve — leave, read and close agent-to-agent handoff notes
- skills_list — list available skill playbooks (Hermes-style reusable workflows)
- skill_load — load the full text of a named skill playbook to follow it
- telegram_status / telegram_accounts / telegram_login_start / telegram_login_confirm / telegram_send / telegram_recent / telegram_logout — user-consented Telegram account management (disabled unless TITAN_TELEGRAM_ENABLED=true; sending only to the .env allowlist)
- mcp_* — tools exposed by connected MCP servers (filesystem, etc.)
- self_heal — SELF-HEALING command runner: on failure it auto-installs missing Python modules and retries until success (use instead of execute_command when a dependency may be missing)
- download_file — SSRF-guarded download of a public http(s) file into the workspace
- start_http_server / stop_http_server — serve the workspace (or any dir) over a local HTTP server
- take_screenshot — capture the primary screen to PNG (Windows)
- self_update — git pull + pip install + run the test suite for the repo owning the workspace
- task_enqueue / task_list / task_stats / task_cancel — the AUTONOMOUS TASK QUEUE: enqueue work for the daemon or other agents (priority, scheduling, retries)
- subagent_delegate / subagent_team / subagent_roles — DEDICATED SUBAGENT STAFF: delegate sub-tasks to named specialists (planner, researcher, coder, reviewer, tester, security, test_writer, summarizer, memory_keeper, cost_watcher, triager, doc_writer, changelogger, deployer, dependency_updater, router) — each with its own persona, tuned run options and enforced tool policy. List roles with subagent_roles; delegate with role= or fan out with subagent_team(tasks, roles).
- subagent_route — INTENT ROUTER: deterministic keyword routing that decides which specialist role(s) should handle an incoming task (primary + supporting + why). Call before delegating a big request.

### SKILLS:
Relevant skill playbooks for the current task are auto-injected into your context
above (### RELEVANT SKILL PLAYBOOKS). Follow them. You may load more via skill_load.

### EFFICIENCY RULES (you are faster than typical agents):
- Never re-run a tool to observe already-known output. Cache results mentally.
- If a single tool call can satisfy the task, do NOT invent extra steps.
- Do not call web_search for general knowledge you already possess; use it only for fresh/live data.
- If the goal is reached, stop immediately and give the final answer — do not add decorative tool calls.
- Use memory_save for important user facts (names, preferences, decisions) so future sessions can recall them.

### FORMATTING & CoT:
- Enclose reasoning, strategy, and reflection inside <thought>...</thought> tags.
- To invoke tools output: <tool_call>{"name": "tool_name", "arguments": {...}}</tool_call> (or native tool_calls when supported).
- After tool execution you will receive the result; analyze it, then continue.
- Final answers must be markdown-formatted, concise but complete, with code blocks when relevant.

### LANGUAGE:
You natively understand Uzbek, English, and Russian. Always respond in the language of the user unless requested otherwise. Be professional, direct, precise, and proactive.

Always remember: You are not just a chatbot — you are an executive agent that gets tasks DONE in the real world, faster and more reliably than any conventional LLM.
"""

REFLECTION_PROMPT = """You are the CRITIC phase of TITAN AGENT. A task was just executed using real tools, and a draft answer was produced.

Review the ENTIRE interaction critically before finalizing:
- Was the user's ORIGINAL request fully satisfied? Check every requirement they asked for.
- Are all claims verified by actual tool results? Remove or fix anything that was only assumed.
- Are there errors, incomplete outputs, missing edge cases, or a better approach?
- Will a human user consider the job DONE after reading your answer?

If anything is missing or wrong, use the tools to fix it NOW (make the needed tool call), or clearly correct/complete your answer.
Then produce the FINAL polished answer to the user (in their language, markdown, complete and precise).
Do not repeat the whole history — output only the final answer (or the tool call needed to finish the job).
"""

DEEP_THINKING_PROMPT = """You are currently operating in DEEP THINKING mode. Elevate your rigor:
- Decompose the problem into explicit sub-problems and reason about each one in detail.
- Consider alternative approaches, edge cases, and failure modes before committing.
- After every step, ask yourself: is there anything unverified, ambiguous, or missing?
- Do not settle for a shallow answer: dig until the result is provably correct and complete.
- You have extra iteration budget — use it deliberately for verification, never for decoration.
"""

DEEP_SEARCH_PROMPT = """You are currently operating in DEEP SEARCH mode. This is a research-heavy task:
- Produce a comprehensive, multi-angle research dossier using deep_search and web_search tools.
- Cross-check claims across multiple sources; prefer verifiable, recently updated information.
- Scrape primary pages when a snippet is insufficient (scrape_webpage tool).
- Structure the final answer with sections and cite the sources you actually retrieved.
- If evidence is thin or conflicting, say so explicitly instead of guessing.
"""

# Effort levels: how hard Titan works on a task (scales iteration budget + rigor).
VALID_EFFORTS = ("auto", "low", "medium", "high", "ultra")

EFFORT_MULTIPLIER = {
    "low": 0.5,
    "medium": 1.0,
    "high": 1.6,
    "ultra": 2.0,
}

EFFORT_PROMPTS = {
    "low": """You are operating at LOW effort: prioritize SPEED and minimal token usage.
- Use the smallest number of tool calls that completes the task; avoid redundant verification.
- Answer directly and concisely; do not expand scope beyond the request.""",
    "high": """You are operating at HIGH effort: work like a careful expert.
- Decompose the problem into explicit sub-problems and reason about each one in detail.
- After every step, ask yourself: is anything unverified, ambiguous, or missing?
- Use your larger iteration budget deliberately for verification, never for decoration.""",
    "ultra": """You are operating at ULTRA effort: maximum thoroughness.
- Be exhaustive: cover edge cases, failure modes, and alternative approaches.
- Verify every claim with tools; do not settle for a shallow answer.
- Review the whole task from the user's perspective before finalizing — if any part of the
  request is unmet, keep working until it is.""",
}


def _resolve_effort(effort: str, mode: str) -> str:
    """Normalize a requested effort level; 'auto' derives from the mode."""
    e = (effort or "auto").strip().lower()
    if e not in VALID_EFFORTS:
        e = "auto"
    if e == "auto":
        # Deep modes are inherently heavy — default them to 'high'.
        e = "high" if mode in ("deep", "deep_search") else "medium"
    return e


def _compute_max_steps(mode: str, effort: str) -> int:
    """Iteration budget = base (mode) scaled by the effort multiplier.

    The multiplier applies ONLY to explicitly chosen effort levels ('low'/
    'high'/'ultra'); 'auto' keeps the classic mode-based budget so deep modes
    behave exactly as before unless the user opts into extra effort.

    Phase 7 (Full Autonomy): the ceiling is now configurable via TITAN_STEP_CAP
    (default 48 — the old hard clamp) and fully removable with
    TITAN_UNLIMITED_STEPS=1, so the agent can keep working until the task is
    provably done instead of stopping at an arbitrary number.

    Phase 8 (FULL ACCESS): TITAN_FULL_ACCESS=1 removes the ceiling entirely AND
    scales the base budget up 4x — no matter how long a task takes, Titan keeps
    iterating (it must still VERIFY and produce a final answer).
    """
    base = MAX_ITERATIONS
    if mode in ("deep", "deep_search"):
        base = min(MAX_ITERATIONS * 2, DEEP_MAX_STEPS_BASE)
    e = (effort or "auto").strip().lower()
    if e not in VALID_EFFORTS:
        e = "auto"
    multiplier = 1.0 if e == "auto" else EFFORT_MULTIPLIER.get(e, 1.0)
    steps = max(5, round(base * multiplier))
    if full_access_enabled():
        # No cap and a 4x larger budget: the agent runs until the task is done.
        return max(steps, round(base * multiplier * 4))
    if UNLIMITED_STEPS:
        # No ceiling: still bounded by base*multiplier growth, but no 48 clamp.
        return steps
    return min(steps, MAX_STEPS_CAP)


# ---- Phase 10: harness hardening helpers --------------------------------

def _msg_cost(m: dict[str, Any]) -> int:
    """Rough char cost of one message (content + inline tool-call args)."""
    cost = len(str(m.get("content") or ""))
    for tc in m.get("tool_calls") or []:
        if isinstance(tc, dict):
            fn = tc.get("function", {}) or {}
            cost += len(str(fn.get("arguments") or ""))
    return cost


CONTEXT_TRIM_MARKER = (
    "...(context trimmed to fit the run budget: earlier tool results were "
    "removed; the task statement and the newest steps remain above)..."
)


def trim_messages_for_context(
    messages: list[dict[str, Any]],
    max_chars: int | None = None,
) -> list[dict[str, Any]]:
    """Keep a run's message list inside a char budget WITHOUT corrupting the
    assistant->tool pairing that OpenAI-compatible APIs require.

    - System messages and the first user task message are never dropped, so
      deep runs stay anchored to the request.
    - The newest rounds are kept first (the active working window).
    - Tool blocks (an assistant message with tool_calls + its following tool
      messages) are trimmed only as a whole unit, so the message array stays
      API-valid after trimming.
    - If anything was dropped, one short marker message is inserted right after
      the head so the model knows earlier context was truncated.
    """
    if not messages:
        return list(messages)
    budget = CONTEXT_BUDGET_CHARS if max_chars is None else int(max_chars)
    total = sum(_msg_cost(m) for m in messages)
    if total <= budget:
        return list(messages)

    head: list[int] = []
    for i, m in enumerate(messages):
        if m.get("role") == "system":
            head.append(i)
    first_user = next(
        (i for i, m in enumerate(messages) if m.get("role") == "user"), None
    )
    if first_user is not None and first_user not in head:
        head.append(first_user)
    head_set = set(head)
    tail_budget = max(0, budget - sum(_msg_cost(messages[i]) for i in head))

    kept: list[int] = []
    kept_set: set[int] = set()
    size = 0
    i = len(messages) - 1
    while i >= 0 and size < tail_budget:
        if i in head_set:
            i -= 1
            continue
        m = messages[i]
        if m.get("role") == "tool":
            # Whole-block atomicity: owning assistant + all of its tool messages.
            block: list[int] = []
            j = i
            while j >= 0 and messages[j].get("role") == "tool":
                block.append(j)
                j -= 1
            if (
                j >= 0
                and messages[j].get("role") == "assistant"
                and messages[j].get("tool_calls")
            ):
                block.append(j)
            block_cost = sum(_msg_cost(messages[k]) for k in block)
            if size + block_cost <= tail_budget:
                for k in block:
                    if k not in kept_set:
                        kept.append(k)
                        kept_set.add(k)
                size += block_cost
            i = j
            continue
        if m.get("role") == "assistant" and m.get("tool_calls"):
            # Its tool block is kept (or dropped) as a unit, never alone.
            i -= 1
            continue
        cost = _msg_cost(m)
        if size + cost <= tail_budget:
            kept.append(i)
            kept_set.add(i)
            size += cost
        i -= 1

    final_idx = sorted(set(head + kept))
    if len(final_idx) == len(messages):
        return list(messages)
    trimmed = [messages[k] for k in final_idx]
    cut = len(head)  # right after the never-dropped head
    trimmed.insert(cut, {"role": "system", "content": CONTEXT_TRIM_MARKER})
    return trimmed


def parse_tool_arguments(raw: Any, tool_name: str = "") -> dict[str, Any] | None:
    """Best-effort repair of an LLM tool arguments payload.

    Returns the dict to execute with, or None when the payload cannot be
    salvaged (the caller then skips the call and reports the raw text instead
    of silently running the tool with empty arguments).

    Handles: empty payload -> {}; dict pass-through (native tool_calls); JSON
    wrapped in code fences / backticks; and a body that contains one balanced
    {...} region. Non-dict JSON (bare string/list) is wrapped as {"value": ...}.
    """
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    s = str(raw).strip()
    if not s:
        return {}
    if s.startswith("```"):
        s = s.strip("`").strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    elif s.startswith("`") and s.endswith("`"):
        s = s[1:-1].strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        pass
    else:
        return obj if isinstance(obj, dict) else {"value": obj}
    start = s.find("{")
    end = s.rfind("}")
    if 0 <= start < end:
        try:
            obj = json.loads(s[start : end + 1])
        except json.JSONDecodeError:
            return None
        return obj if isinstance(obj, dict) else {"value": obj}
    return None


_CONTEXT_OVERFLOW_MARKERS = (
    "context length",
    "context_length",
    "maximum context",
    "max context",
    "context window",
    "token limit",
    "token_limit",
    "too many tokens",
    "input is too long",
    "prompt is too long",
)

class AgentEvent:
    def __init__(self, event_type: str, data: Any):
        self.type = event_type
        self.data = data

    def to_dict(self):
        return {"type": self.type, "data": self.data}

class TitanAgent:
    def __init__(
        self,
        llm: LLMClient | None = None,
        tools: ToolRegistry | None = None,
        mcp: MCPManager | None = None,
        memory: MemoryManager | None = None,
        skills: SkillRegistry | None = None,
        telegram: TelegramManager | None = None,
        core_memory: MemorySystem | None = None,
        core_memory_path: Path | str | None = None,
        git_root: Path | str | None = None,
        auto_commit: bool | None = None,
        checkpoint: CheckpointStore | None = None,
        checkpoint_path: Path | str | None = None,
        tool_policy: Any | None = None,
        hitl: HumanInTheLoop | None = None,
        hitl_timeout: float = 120.0,
    ):
        self.llm = llm or LLMClient()
        self.tools = tools or ToolRegistry()
        self.mcp = mcp or MCPManager()
        self.memory = memory or MemoryManager()
        self.skills = skills or SkillRegistry()
        self.telegram = telegram or TelegramManager()
        # Phase 9: per-role tool policy (Allowed/blocked sets enforced in
        # execute_tool_unified AND reflected in the model's tool catalog).
        self.tool_policy = tool_policy
        # Phase 14: Human-in-the-loop approval gate. Wired onto the tool registry
        # (single approval point for BOTH the classic loop and the structured
        # strategy path — ToolBridge defers via defer_approval=True) so sensitive
        # tool calls can wait for explicit human consent instead of hard-failing.
        self.hitl = hitl
        self.hitl_timeout = hitl_timeout
        if hitl is not None:
            attach = getattr(self.tools, "attach_hitl", None)
            if callable(attach):
                try:
                    attach(hitl, hitl_timeout)
                except Exception as exc:  # noqa: BLE001 - HITL is best-effort
                    log.warning("could not attach HITL to tool registry: %s", exc)
        self.system_prompt = TITAN_SYSTEM_PROMPT
        # ---- Phase 4: MemGPT-style core memory + Git-first workflow ----
        self._core_memory = core_memory
        self._core_memory_loaded = core_memory is not None
        self.core_memory_path = Path(core_memory_path) if core_memory_path else (WORKSPACE_DIR / "core_memory.db")
        self.git_root = Path(git_root).resolve() if git_root else WORKSPACE_DIR
        self._auto_commit = auto_commit if auto_commit is not None else (
            os.getenv("TITAN_GIT_AUTO_COMMIT", "").strip().lower() in ("1", "true", "yes")
        )
        # ---- Phase 5: Devin-style session checkpoints / resume ----
        self._checkpoint = checkpoint
        self._checkpoint_loaded = checkpoint is not None
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else (WORKSPACE_DIR / "checkpoints.db")

    @property
    def core_memory(self) -> MemorySystem | None:
        """Phase 4: episodic/semantic store, lazily opened on first use so
        construction never touches disk (memory must never break the agent)."""
        if self._core_memory_loaded:
            return self._core_memory
        self._core_memory_loaded = True
        try:
            self._core_memory = MemorySystem(self.core_memory_path)
        except Exception as exc:  # noqa: BLE001 - memory is best-effort
            log.warning("core memory unavailable: %s", exc)
            self._core_memory = None
        return self._core_memory

    @property
    def auto_commit(self) -> bool:
        """Whether completed runs auto-commit workspace changes (Aider-style)."""
        return self._auto_commit

    @property
    def checkpoint_store(self) -> CheckpointStore | None:
        """Phase 5: Devin-style checkpoint store, lazily opened on first use."""
        if self._checkpoint_loaded:
            return self._checkpoint
        self._checkpoint_loaded = True
        try:
            self._checkpoint = CheckpointStore(self.checkpoint_path)
        except Exception as exc:  # noqa: BLE001 - checkpointing is best-effort
            log.warning("checkpoint store unavailable: %s", exc)
            self._checkpoint = None
        return self._checkpoint

    def _build_memory_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "memory_save",
                    "description": "Saves a fact or piece of information into Titan's long-term persistent memory so it is remembered in all future sessions (e.g. user name, preferences, decisions). Use 'scope' to target a Memory Vault scope: global (everything), project (this repo), team (shared), user (personal).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "Unique short key for the fact (e.g. 'user_name')."},
                            "value": {"type": "string", "description": "The fact content to remember."},
                            "category": {"type": "string", "description": "Optional category (e.g. 'profile', 'project', 'preference')."},
                            "scope": {"type": "string", "description": "Memory Vault scope: global, project, team, user (default global)."}
                        },
                        "required": ["key", "value"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_search",
                    "description": "Searches Titan's long-term persistent memory for facts saved in earlier sessions. Set 'scope' to search only that Memory Vault scope, or omit to search everything.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Text to search for in remembered facts."},
                            "limit": {"type": "integer", "description": "Max results to return (default 5)."},
                            "scope": {"type": "string", "description": "Optional Memory Vault scope filter: global, project, team, user."}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "vault_list",
                    "description": "Lists facts in the Memory Vault, optionally filtered by scope (global/project/team/user).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "scope": {"type": "string", "description": "Optional scope filter: global, project, team, user."},
                            "limit": {"type": "integer", "description": "Max results (default 50)."}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "handoff_create",
                    "description": "Leaves a handoff note for the next agent / session (Hermes handoff pattern): a short 'where things stand + what to do next' pass-along.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Short title for the handoff."},
                            "content": {"type": "string", "description": "The handoff note: current state, decisions, next steps."},
                            "scope": {"type": "string", "description": "Optional scope: global, project, team, user (default global)."}
                        },
                        "required": ["title", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "handoff_list",
                    "description": "Lists open handoff notes left by previous agents/sessions (use at the START of a task to continue prior work).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Optional status filter: open or resolved (default open)."}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "handoff_resolve",
                    "description": "Marks a handoff note as resolved/cancelled once its work is complete.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "description": "The handoff id."},
                            "status": {"type": "string", "description": "resolved or cancelled (default resolved)."}
                        },
                        "required": ["id"]
                    }
                }
            }
        ]

    def _build_skill_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "skills_list",
                    "description": "Lists all available skill playbooks (Hermes-style reusable workflows: research-ops, github-ops, coding-rules, terminal-ops, security-ops, planning-ops, ...).",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "skill_load",
                    "description": "Loads the full text of a named skill playbook so you can follow its workflow exactly.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "The skill name (e.g. 'research-ops')."}
                        },
                        "required": ["name"]
                    }
                }
            }
        ]

    def _build_telegram_tool_definitions(self) -> list[dict[str, Any]]:
        """Telegram account manager tools. Every tool is consent-gated: it refuses
        to run unless TITAN_TELEGRAM_ENABLED=true in .env, and sending is limited
        to TITAN_TELEGRAM_SEND_ALLOWLIST targets."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "telegram_status",
                    "description": "Shows whether Telegram control is enabled, credentials are set, how many accounts are registered, and the send-allowlist. No secrets are ever shown.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_accounts",
                    "description": "Lists the user's registered Telegram account sessions (labels only, with masked phone/username). Never shows credentials.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_login_start",
                    "description": "Starts logging in a NEW Telegram account under a label: Telegram sends a one-time code to the given phone. Then call telegram_login_confirm with the code the USER received. Never guess the code — only use a code the user explicitly provides.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Short name for this account, e.g. 'work'."},
                            "phone": {"type": "string", "description": "The user's phone number in international format, e.g. +998901234567."}
                        },
                        "required": ["label", "phone"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_login_confirm",
                    "description": "Completes a telegram_login_start with the one-time code that Telegram sent to the user's phone and that the USER explicitly provided.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "The same label used in telegram_login_start."},
                            "code": {"type": "string", "description": "The one-time login code the user received and shared."}
                        },
                        "required": ["label", "code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_send",
                    "description": "Sends a Telegram message from a registered account to ONE target. Works ONLY if the target is in TITAN_TELEGRAM_SEND_ALLOWLIST in .env — otherwise it is refused. Never used for broadcasting.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Account label."},
                            "target": {"type": "string", "description": "Recipient username (e.g. 'titan_bot') or numeric id."},
                            "text": {"type": "string", "description": "Message text."}
                        },
                        "required": ["label", "target", "text"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_recent",
                    "description": "Read-only: returns the most recent messages from a registered account's own dialogs (senders masked).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Account label."},
                            "limit": {"type": "integer", "description": "Max messages (default 10, max 25)."}
                        },
                        "required": ["label"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_logout",
                    "description": "Removes a registered Telegram account session. Set delete=true to also log the account out of Telegram entirely.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Account label to remove."},
                            "delete": {"type": "boolean", "description": "true = log out on Telegram too; default false = remove local session only."}
                        },
                        "required": ["label"]
                    }
                }
            },
        ]

    def _build_git_tool_definitions(self) -> list[dict[str, Any]]:
        """Git tools — Aider-style git-first workflow (read-only + explicit commit)."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "git_status",
                    "description": "Shows the current git working-tree state (modified/untracked files) for the workspace repository.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "git_diff",
                    "description": "Shows uncommitted changes (diff --stat) in the workspace repository.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "git_commit",
                    "description": "Commits all current workspace changes with a descriptive message (Aider-style git-first workflow). Use after writing or editing files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "Concise commit message describing the change."}
                        },
                        "required": ["message"],
                    },
                },
            },
        ]

    def _build_tools_list(self) -> list[dict[str, Any]]:
        all_tools = list(self.tools.get_tool_definitions())
        # Add memory tools (agent-level, routed through MemoryManager)
        all_tools.extend(self._build_memory_tool_definitions())
        # Add skill tools (agent-level, routed through SkillRegistry)
        all_tools.extend(self._build_skill_tool_definitions())
        # Add Telegram tools (agent-level, consent-gated through TelegramManager)
        all_tools.extend(self._build_telegram_tool_definitions())
        # Add Git tools (agent-level, Aider-style git-first workflow)
        all_tools.extend(self._build_git_tool_definitions())
        # Add MCP tools if connected
        all_tools.extend(self.mcp.get_all_tools())
        # Phase 9: drop tools the role may not use (visible AND enforced).
        if self.tool_policy is not None:
            all_tools = self.tool_policy.filter_definitions(all_tools)
        return all_tools

    def _policy_allows(self, name: str) -> bool:
        return self.tool_policy is None or self.tool_policy.allows(name)

    def _build_tool_catalog_text(self) -> str:
        """Compact live tool catalog appended to the system prompt each turn."""
        lines = []
        for t in self.tools.get_tool_definitions():
            fn = t.get("function", {})
            if not self._policy_allows(str(fn.get("name", ""))):
                continue
            params = fn.get("parameters", {}).get("properties", {})
            param_hint = ", ".join(params.keys()) if params else "no params"
            lines.append(f"- {fn.get('name')}({param_hint}): {fn.get('description', '')}")
        for t in self._build_memory_tool_definitions():
            fn = t.get("function", {})
            if not self._policy_allows(str(fn.get("name", ""))):
                continue
            params = fn.get("parameters", {}).get("properties", {})
            param_hint = ", ".join(params.keys()) if params else "no params"
            lines.append(f"- {fn.get('name')}({param_hint}): {fn.get('description', '')}")
        for t in self._build_skill_tool_definitions():
            fn = t.get("function", {})
            if not self._policy_allows(str(fn.get("name", ""))):
                continue
            params = fn.get("parameters", {}).get("properties", {})
            param_hint = ", ".join(params.keys()) if params else "no params"
            lines.append(f"- {fn.get('name')}({param_hint}): {fn.get('description', '')}")
        for t in self._build_telegram_tool_definitions():
            fn = t.get("function", {})
            if not self._policy_allows(str(fn.get("name", ""))):
                continue
            params = fn.get("parameters", {}).get("properties", {})
            param_hint = ", ".join(params.keys()) if params else "no params"
            lines.append(f"- {fn.get('name')}({param_hint}): {fn.get('description', '')}")
        for t in self._build_git_tool_definitions():
            fn = t.get("function", {})
            if not self._policy_allows(str(fn.get("name", ""))):
                continue
            params = fn.get("parameters", {}).get("properties", {})
            param_hint = ", ".join(params.keys()) if params else "no params"
            lines.append(f"- {fn.get('name')}({param_hint}): {fn.get('description', '')}")
        mcp_tools = self.mcp.get_all_tools()
        if mcp_tools:
            lines.append("\nMCP server tools:")
            for t in mcp_tools:
                fn = t.get("function", {})
                if not self._policy_allows(str(fn.get("name", ""))):
                    continue
                lines.append(f"- {fn.get('name')}: {fn.get('description', '')}")
        return "\n".join(lines)

    def _build_structured_context(self, user_input: str, mode: str, effort: str) -> str:
        """System context for the Phase 3 structured engines: agent identity,
        live tool catalog, auto-recalled facts and skill playbooks. Mirrors the
        classic loop's system assembly so structured runs stay as informed."""
        content = (
            self.system_prompt
            + "\n\n### LIVE TOOL CATALOG (all tools currently available):\n"
            + self._build_tool_catalog_text()
        )
        recalled = self.memory.recall_relevant(user_input, limit=5)
        if recalled:
            content += "\n\n### REMEMBERED FACTS (from long-term memory, relevant to this request):\n"
            for f in recalled:
                content += f"- [{f['category']}] {f['key']}: {f['value']}\n"
            content += "(Use these facts as true context; do not claim you read them fresh.)"
        core_block = self._core_recall_block(user_input)
        if core_block:
            content += core_block
        skill_block = self.skills.build_system_block(user_input)
        if skill_block:
            content += skill_block
        if mode == "deep":
            content += "\n\n" + DEEP_THINKING_PROMPT
        elif mode == "deep_search":
            content += "\n\n" + DEEP_SEARCH_PROMPT
        if effort in EFFORT_PROMPTS:
            content += "\n\n" + EFFORT_PROMPTS[effort]
        return content

    def _core_recall_block(self, query: str, limit: int = 3) -> str:
        """Past runs & lessons from Phase 4 core memory. Empty unless records
        exist, so the classic loop's prompt is untouched for fresh stores."""
        mem = self.core_memory  # lazy open
        if mem is None:
            return ""
        try:
            hits = mem.recall(query, limit=limit)
        except Exception as exc:  # noqa: BLE001 - recall must never break a run
            log.debug("core recall failed: %s", exc)
            return ""
        if not hits:
            return ""
        lines = [f"- {r.content[:300]}" for r in hits]
        return "\n\n### PAST RUNS & LESSONS (agent memory, relevant to this task):\n" + "\n".join(lines)

    async def _finalize_run(
        self,
        session_id: str,
        user_input: str,
        final_text: str,
        mode: str,
        strategy: str,
        auto_commit: bool,
    ) -> None:
        """After a completed run: record an episodic core-memory entry and,
        when auto-commit is on, commit workspace changes (Aider-style)."""
        if final_text:
            mem = self.core_memory  # lazy open
            if mem is not None:
                try:
                    mem.remember(
                        content=f"task[{session_id}]: {user_input[:200]}\nresult: {final_text[:1200]}",
                        kind=MemoryKind.EPISODIC,
                        importance=0.4,
                        scope="agent",
                        metadata={"session": session_id, "mode": mode, "strategy": strategy},
                    )
                except Exception as exc:  # noqa: BLE001 - memory is best-effort
                    log.warning("core memory write failed: %s", exc)
        if auto_commit and final_text:
            try:
                await asyncio.to_thread(git_auto_commit, self.git_root, user_input)
            except Exception as exc:  # noqa: BLE001 - commit must never kill the run
                log.warning("auto-commit failed: %s", exc)

    def _checkpoint_load(self, session_id: str) -> RunCheckpoint | None:
        """Best-effort load of a session's checkpoint; never raises."""
        store = self.checkpoint_store
        if store is None:
            return None
        try:
            return store.load(session_id)
        except Exception as exc:  # noqa: BLE001
            log.debug("checkpoint load failed for %s: %s", session_id, exc)
            return None

    def _checkpoint_save(
        self,
        *,
        session_id: str,
        user_input: str,
        mode: str,
        effort: str,
        strategy: str,
        messages: list[dict[str, Any]],
        steps_done: int = 0,
        tools_used: list[str] | None = None,
        status: str = "running",
        final_answer: str | None = None,
    ) -> None:
        """Best-effort persist of the run's live state (always-on checkpointing)."""
        store = self.checkpoint_store
        if store is None:
            return
        try:
            trimmed = list(messages)[-CHECKPOINT_MAX_MESSAGES:]
            store.save(
                RunCheckpoint(
                    session_id=session_id,
                    user_input=user_input,
                    mode=mode,
                    effort=effort,
                    strategy=strategy,
                    messages=trimmed,
                    steps_done=int(steps_done),
                    tools_used=[str(t) for t in (tools_used or [])],
                    status=status,
                    final_answer=final_answer,
                )
            )
        except Exception as exc:  # noqa: BLE001 - checkpointing must never break a run
            log.debug("checkpoint save failed for %s: %s", session_id, exc)

    async def _approval_gate(self, name: str, args: dict[str, Any]) -> bool | None:
        """Phase 14: single HITL approval decision point for sensitive tools.

        Returns:
          None  -> no approval needed (or gate disabled / under FULL access)
          True  -> explicitly APPROVED by the human
          False -> denied or timed out (caller must not execute)
        """
        try:
            if full_access_enabled():
                return None  # Phase 8: approvals are auto-granted in FULL access
            resource = str(args.get("command", "")) if name == "execute_command" else name
            decision = PolicyEngine().check(
                name,
                resource,
                json.dumps(args, default=str),
                access=PolicyEngine.ACCESS_NORMAL,
            )
            if decision.decision != Decision.REQUIRE_APPROVAL:
                return None
            req = self.hitl.request(
                name,
                resource,
                details={"args": args},
                reason="; ".join(decision.reasons or []) or "requires human approval",
            )
            req = await self.hitl.wait(req, timeout=self.hitl_timeout)
            return req.status == ApprovalStatus.APPROVED
        except Exception as exc:  # noqa: BLE001 - the gate must never break a run
            log.debug("approval gate failed for %s: %s", name, exc)
            return None

    async def execute_tool_unified(self, name: str, args: dict[str, Any]) -> str:
        # Phase 9: per-role tool policy enforced for EVERY tool family
        # (terminal / memory / skill / telegram / git / mcp) — a researcher
        # cannot commit, a reviewer cannot write.
        if not self._policy_allows(name):
            return f"Error: tool '{name}' is outside this subagent's role and was blocked by tool policy."
        # Phase 14: Human-in-the-loop approval gate. Executes for every tool
        # call funnel (classic loop, structured strategy, cron, queue) so the
        # live agent truly waits for a human instead of silently doing nothing.
        # When no HITL is wired (tests / headless) today's behavior is kept.
        if self.hitl is not None:
            granted = await self._approval_gate(name, args)
            if granted is False:
                return (
                    "Error: approval required but not granted "
                    f"(tool='{name}' was not approved by the human)."
                )
        if name == "memory_save":
            key = str(args.get("key", "")).strip()
            value = str(args.get("value", "")).strip()
            category = str(args.get("category", "agent")).strip() or "agent"
            scope = args.get("scope")
            if not key or not value:
                return "Error: memory_save requires both 'key' and 'value'."
            self.memory.remember_fact(key, value, category, scope=scope)
            scope_note = f" (scope: {scope})" if scope else ""
            return f"Saved to memory: {key} = {value} (category: {category}){scope_note}"
        if name == "memory_search":
            query = str(args.get("query", "")).strip()
            limit = int(args.get("limit", 5) or 5)
            scope = args.get("scope")
            if not query:
                return "Error: memory_search requires 'query'."
            facts = self.memory.search_knowledge(query, limit=limit, scope=scope)
            if not facts:
                return "No matching facts found in memory."
            return "\n".join(
                f"- [{f.get('category')}] {f['key']}: {f['value']}" for f in facts
            )
        if name == "vault_list":
            scope = args.get("scope")
            limit = int(args.get("limit", 50) or 50)
            facts = self.memory.vault_list(scope=scope, limit=limit)
            if not facts:
                return "Memory Vault is empty."
            return "\n".join(
                f"- [{f['scope']}/{f['category']}] {f['key']}: {f['value']}" for f in facts
            )
        if name == "handoff_create":
            title = str(args.get("title", "")).strip()
            content = str(args.get("content", "")).strip()
            scope = args.get("scope")
            if not title or not content:
                return "Error: handoff_create requires both 'title' and 'content'."
            hid = self.memory.create_handoff(title, content, scope=scope or "global")
            return f"Handoff created (id: {hid}): {title}"
        if name == "handoff_list":
            status = args.get("status")
            msgs = self.memory.list_handoffs(status=status or "open")
            if not msgs:
                return "No handoff notes found."
            return "\n".join(
                f"- [{m['id']}] ({m['status']}) {m['title']}:\n  {m['content']}" for m in msgs
            )
        if name == "handoff_resolve":
            hid = int(args.get("id", 0) or 0)
            status = str(args.get("status", "resolved")).strip()
            if hid <= 0:
                return "Error: handoff_resolve requires a valid 'id'."
            ok = self.memory.resolve_handoff(hid, status=status)
            return f"Handoff {hid} marked {status}." if ok else f"Handoff {hid} not found."
        if name == "skills_list":
            skills = self.skills.list_skills()
            if not skills:
                return "No skill playbooks available."
            return "\n".join(
                f"- {s['name']}: {s['description']}" for s in skills
            )
        if name == "skill_load":
            skill_name = str(args.get("name", "")).strip()
            if not skill_name:
                return "Error: skill_load requires 'name'."
            skill = self.skills.get_skill(skill_name)
            if skill is None:
                names = ", ".join(s["name"] for s in self.skills.list_skills()) or "none loaded"
                return f"Unknown skill '{skill_name}'. Available: {names}"
            return skill.full_text()
        if name.startswith("telegram_"):
            try:
                return await self._dispatch_telegram(name, args)
            except TelegramError as e:
                return f"Telegram: {e}"
        if name.startswith("git_"):
            return await self._dispatch_git(name, args)
        if name.startswith("mcp_"):
            return await self.mcp.execute_tool(name, args)
        else:
            return await self.tools.execute_tool(name, args)

    async def _dispatch_git(self, name: str, args: dict[str, Any]) -> str:
        """Aider-style git tools. Blocking git calls run in a worker thread so
        the event loop keeps streaming."""
        root = self.git_root
        if name == "git_status":
            return await asyncio.to_thread(git_status, root)
        if name == "git_diff":
            return await asyncio.to_thread(git_diff, root)
        if name == "git_commit":
            message = str(args.get("message", "")).strip()
            if not message:
                return "Error: git_commit requires a 'message'."
            return await asyncio.to_thread(git_commit, root, message)
        return f"Unknown git tool '{name}'."

    async def _dispatch_telegram(self, name: str, args: dict[str, Any]) -> str:
        """Consent-gated Telegram dispatch. Every call is wrapped by the caller
        with TelegramError -> friendly message."""
        tg = self.telegram
        if name == "telegram_status":
            s = tg.status()
            allow = ", ".join(s["send_allowlist"]) or "(read-only — allowlist empty)"
            state = "ENABLED" if s["enabled"] else "DISABLED (set TITAN_TELEGRAM_ENABLED=true in .env)"
            creds = "set" if s["credentials_set"] else "MISSING (TITAN_TELEGRAM_API_ID / _HASH in .env)"
            return (
                f"Telegram control: {state}\n"
                f"API credentials: {creds}\n"
                f"Registered accounts: {s['sessions']}\n"
                f"Send allowlist: {allow}\n"
                f"Session dir: {s['session_dir']}"
            )
        if name == "telegram_accounts":
            accs = tg.list_accounts()
            if not accs:
                return "No Telegram accounts registered yet. Use telegram_login_start to add one."
            return "\n".join(
                f"- {a['label']} | phone: {a['phone']} | username: {a['username']} (added {a.get('added','?')})"
                for a in accs
            )
        if name == "telegram_login_start":
            label = str(args.get("label", "")).strip()
            phone = str(args.get("phone", "")).strip()
            res = await tg.login_start(label, phone)
            return (
                f"Login code requested for '{res['label']}'. "
                f"IMPORTANT: ask the user for the code Telegram sent to their phone "
                f"and call telegram_login_confirm(label='{res['label']}', code=...) — "
                f"never guess or reuse a code."
            )
        if name == "telegram_login_confirm":
            label = str(args.get("label", "")).strip()
            code = str(args.get("code", "")).strip()
            if not label or not code:
                return "Error: telegram_login_confirm requires 'label' and 'code'."
            res = await tg.login_confirm(label, code)
            return (
                f"Account '{res['label']}' logged in (phone: {res['phone']}, "
                f"username: {res['username']}). You can now use telegram_recent / "
                f"telegram_send (allowlist-gated)."
            )
        if name == "telegram_send":
            label = str(args.get("label", "")).strip()
            target = str(args.get("target", "")).strip()
            text = str(args.get("text", "")).strip()
            if not label or not target or not text:
                return "Error: telegram_send requires 'label', 'target' and 'text'."
            res = await tg.send_message(label, target, text)
            return f"Sent {res['chars']} chars to @{res['target']} from '{res['label']}'."
        if name == "telegram_recent":
            label = str(args.get("label", "")).strip()
            limit = int(args.get("limit", 10) or 10)
            if not label:
                return "Error: telegram_recent requires 'label'."
            msgs = await tg.recent_messages(label, limit=limit)
            if not msgs:
                return "No recent messages found for that account."
            return "\n".join(
                f"{m['n']}. [{m['date']}] {m['from']}: {m['text']}" for m in msgs
            )
        if name == "telegram_logout":
            label = str(args.get("label", "")).strip()
            delete = bool(args.get("delete", False))
            if not label:
                return "Error: telegram_logout requires 'label'."
            res = await tg.logout(label, delete=delete)
            return f"Account '{res['label']}': {res['status']}."
        return f"Unknown telegram tool '{name}'."

    async def _emit_tool_results(
        self,
        response,
        messages: list[dict[str, Any]],
        iteration: int
    ) -> AsyncGenerator[AgentEvent, None]:
        """Executes all tool_calls inside `response` IN PARALLEL and streams
        events. Mutates `messages` in place.

        Phase 10: calls whose arguments cannot be parsed as JSON are SKIPPED
        (never executed with empty arguments). The raw payload is reported back
        to the model so it can resend a valid call. Every tool_call_id still
        receives exactly one follow-up tool message, keeping the assistant->tool
        pairing valid for the next model request.
        """
        assistant_msg = {
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": response.tool_calls
        }
        messages.append(assistant_msg)

        parsed = []
        for tool_call in response.tool_calls:
            fn = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
            t_name = fn.get("name", "")
            t_args = parse_tool_arguments(fn.get("arguments", "{}"), t_name)
            parsed.append((tool_call, t_name, t_args))

        # Emit all scheduled tool_call events first
        for tool_call, t_name, t_args in parsed:
            yield AgentEvent("tool_call", {"name": t_name, "arguments": t_args})

        runnable = [p for p in parsed if p[2] is not None]
        skipped = [p for p in parsed if p[2] is None]

        if len(runnable) > 1:
            yield AgentEvent("status", f"Running {len(runnable)} tools in parallel...")
        elif runnable:
            yield AgentEvent("status", f"Running tool: {runnable[0][1]}...")
        elif skipped:
            yield AgentEvent(
                "status",
                f"Skipping {len(skipped)} tool call(s) with unparsable arguments.",
            )

        # Execute all runnable tools concurrently
        async def _run_one(tool_call, t_name, t_args):
            try:
                result = await self.execute_tool_unified(t_name, t_args)
                return tool_call, t_name, result
            except (RuntimeError, OSError, ValueError) as e:
                return tool_call, t_name, f"Error: {e!s}"

        results = await asyncio.gather(*(_run_one(*p) for p in runnable))
        result_map = {id(r[0]): r[2] for r in results}

        # Emit results and append tool messages in ORIGINAL call order, so every
        # tool_call_id gets exactly one follow-up message.
        for tool_call, t_name, t_args in parsed:
            if t_args is None:
                raw = ""
                if isinstance(tool_call, dict):
                    raw = str(tool_call.get("function", {}).get("arguments", ""))
                result = (
                    "Skipped: tool arguments could not be parsed as valid JSON. "
                    f"Raw arguments (truncated): {raw[:400]!r}"
                )
                yield AgentEvent("tool_result", {"name": t_name, "result": result})
            else:
                result = result_map.get(id(tool_call), "Error: tool call vanished.")
                yield AgentEvent("tool_result", {"name": t_name, "result": result})
            messages.append({
                "role": "tool",
                "tool_call_id": (
                    tool_call.get("id", f"call_{iteration}")
                    if isinstance(tool_call, dict) else f"call_{iteration}"
                ),
                "name": t_name,
                "content": str(result)
            })

    async def _chat_with_recovery(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> tuple[Any, list[dict[str, Any]], list[str]]:
        """Robust model call for one loop iteration.

        Returns (response, working_messages, status_notes).

        Phase 10 hardening:
        - Transient network errors (aiohttp.ClientError / OSError / timeouts)
          retry with linear backoff up to LLM_TRANSIENT_RETRIES — a single
          hiccup no longer kills an entire deep run.
        - Context-length errors trigger an automatic trim_messages_for_context
          pass + one retry, so an over-budget run degrades gracefully to a
          usable window instead of dying mid-task.
        - API-level failures (401/403/...) and context errors that trimming
          cannot fix still fail fast.
        """
        working = list(messages)
        notes: list[str] = []
        transient = (aiohttp.ClientError, OSError, asyncio.TimeoutError)
        overflow_left = 6  # bounded halving loop on repeated context overflows

        for attempt in range(LLM_TRANSIENT_RETRIES + 1):
            try:
                response = await self.llm.chat_completion(working, tools=tools)
                return response, working, notes
            except transient as e:
                if attempt >= LLM_TRANSIENT_RETRIES:
                    raise
                notes.append(
                    f"LLM transient error, retrying ({attempt + 1}/"
                    f"{LLM_TRANSIENT_RETRIES}): {e!s}"
                )
                await asyncio.sleep(0.75 * (attempt + 1))
            except RuntimeError as e:
                lowered = str(e).lower()
                if not any(marker in lowered for marker in _CONTEXT_OVERFLOW_MARKERS):
                    raise
                if overflow_left <= 0:
                    raise
                overflow_left -= 1
                # Progressive halving: shrink to ~half the current size on every
                # overflow, because we do not know the provider's real window.
                # Bounded retries guarantee termination while still landing under
                # it for reasonable windows.
                current = sum(_msg_cost(m) for m in working)
                target = max(512, current // 2)
                trimmed = trim_messages_for_context(working, max_chars=target)
                if len(trimmed) < len(working):
                    working = trimmed
                    notes.append(
                        "Context overflow detected - trimmed older tool "
                        f"rounds to ~{len(trimmed)} messages and retrying."
                    )
                    continue
                raise
        raise RuntimeError("LLM unreachable after all retries.")  # pragma: no cover

    async def run_task(
        self,
        user_input: str,
        session_id: str = "default_session",
        mode: str = "fast",
        effort: str = "auto",
        strategy: str = "auto",
        auto_commit: bool | None = None,
        resume: bool = False,
        system_extra: str | None = None
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        Executes a user request with autonomous multi-step reasoning, tool execution,
        and a critical reflection (self-review) pass before the final answer.
        mode: "fast" | "deep" | "deep_search"
        effort: "auto" | "low" | "medium" | "high" | "ultra" — scales the iteration
                budget and rigor of the run ('auto' derives from the mode).
        strategy: "auto" | "plan" | "react" | "tot" — Phase 3 structured reasoning.
                'auto' keeps the classic prompt-driven loop (backward compatible);
                'plan' builds a step plan then executes it; 'react' uses the
                structured ReAct engine; 'tot' explores strategies with
                Tree-of-Thoughts first, then executes with tools. All structured
                strategies run the Phase 2 core engines with policy guardrails.
        auto_commit: None = instance default (env TITAN_GIT_AUTO_COMMIT); True/False
                overrides. When on, workspace changes are committed after a
                successful run (Aider-style git-first workflow).
        resume: when True (Devin/Claude-Code-style continuity), the run restores
                this session's checkpoint (live messages + step count) and
                continues from where it stopped. A session already marked done
                returns its saved final answer instead of re-running.
        Yields AgentEvent objects for real-time streaming to Web UI / CLI.
        """
        if mode not in ("fast", "deep", "deep_search"):
            mode = "fast"
        raw_effort = effort or "auto"  # budget scaling needs to know if effort was explicit
        effort = _resolve_effort(effort, mode)
        strategy = (strategy or "auto").strip().lower()
        if strategy not in ("auto", "plan", "react", "tot"):
            strategy = "auto"
        auto_commit = self._auto_commit if auto_commit is None else auto_commit

        # ---- Phase 5: a session already completed returns its saved result ----
        if resume:
            cp = self._checkpoint_load(session_id)
            if cp is not None and cp.status == "done" and cp.final_answer:
                yield AgentEvent("status", f"Session '{session_id}' already completed — returning saved result.")
                yield AgentEvent("final_answer", cp.final_answer)
                self.memory.add_message(session_id, "assistant", cp.final_answer)
                return

        # Save user message to memory
        self.memory.add_message(session_id, "user", user_input)

        # Retrieve conversation history
        history = self.memory.get_recent_messages(session_id, limit=10)

        # Format messages for LLM
        catalog_text = self._build_tool_catalog_text()
        system_content = (
            self.system_prompt
            + "\n\n### LIVE TOOL CATALOG (all tools currently available):\n"
            + catalog_text
        )
        # Phase 9: role persona overlay (subagent specialist identity) — placed
        # right after the base identity so it steers behaviour from the start.
        if system_extra:
            system_content += "\n\n" + system_extra
        # Auto-recall: seed remembered facts relevant to this request (Memory
        # Agent pattern) so the model starts the turn already knowing the user.
        recalled = self.memory.recall_relevant(user_input, limit=5)
        if recalled:
            recall_block = "\n\n### REMEMBERED FACTS (from long-term memory, relevant to this request):\n"
            for f in recalled:
                recall_block += f"- [{f['category']}] {f['key']}: {f['value']}\n"
            recall_block += "(Use these facts as true context; do not claim you read them fresh.)"
            system_content += recall_block
        core_block = self._core_recall_block(user_input)
        if core_block:
            system_content += core_block
        # Auto-skill load: inject relevant Hermes-style playbooks for this task
        skill_block = self.skills.build_system_block(user_input)
        if skill_block:
            system_content += skill_block
        if mode == "deep":
            system_content += "\n\n" + DEEP_THINKING_PROMPT
        elif mode == "deep_search":
            system_content += "\n\n" + DEEP_SEARCH_PROMPT
        # Effort-level guidance (LOW/HIGH/ULTRA)
        if effort in EFFORT_PROMPTS:
            system_content += "\n\n" + EFFORT_PROMPTS[effort]
        # Phase 8: Full Access mode — every capability boundary is removed.
        if full_access_enabled():
            system_content += (
                "\n\n### FULL ACCESS MODE ACTIVE (TITAN_FULL_ACCESS=1)\n"
                "Every capability boundary is removed for this run:\n"
                "- No step budget limit — keep working until the task is VERIFIABLY complete.\n"
                "- No 45s command timeout (up to 10 minutes per command).\n"
                "- Approvals are auto-granted (delete_file / screenshot / ports / paths).\n"
                "- Downloads have no 100 MB cap; token rate limiting is disabled.\n"
                "- Subagent teams may run up to 8 workers in parallel.\n"
                "Use the extra scope deliberately, and still VERIFY every claim with tools before reporting."
            )

        messages = [{"role": "system", "content": system_content}]
        for msg in history:
            m_dict = {"role": msg["role"], "content": msg["content"]}
            messages.append(m_dict)

        # ---- Phase 5: Devin-style resume — restore the session's live state ----
        if resume:
            cp = self._checkpoint_load(session_id)
            if cp is not None and cp.messages:
                yield AgentEvent(
                    "status",
                    f"Resuming session '{session_id}' from checkpoint ({cp.steps_done} "
                    f"steps done, last status: {cp.status}).",
                )
                messages = [
                    {"role": m["role"], "content": m["content"]}
                    for m in cp.messages
                ][-CHECKPOINT_MAX_MESSAGES:]
        # Always-on checkpointing (Devin-style): persist run state so an interrupted
        # session can be resumed without losing work.
        self._checkpoint_save(
            session_id=session_id,
            user_input=user_input,
            mode=mode,
            effort=effort,
            strategy=strategy,
            messages=messages,
            steps_done=0,
            status="running",
        )

        max_steps = _compute_max_steps(mode, raw_effort)

        # ---- Phase 3: structured reasoning (core engines) -------------------
        # Explicit strategy (plan/react/tot) runs the Phase 2 core engines with
        # policy guardrails. 'auto' keeps the classic loop below untouched.
        if strategy != "auto":
            yield AgentEvent("status", f"Structured reasoning engaged (strategy={strategy}, effort={effort}, max steps: {max_steps})")
            structured_final = None
            try:
                from .structured import StructuredEngine
                engine = StructuredEngine(
                    self.llm,
                    self.execute_tool_unified,
                    self._build_tools_list,
                    session_id=session_id,
                    # Phase 14: defer approval to the registry's HITL gate so the
                    # structured and classic paths share ONE approval decision.
                    hitl=None,
                    hitl_timeout=self.hitl_timeout,
                    defer_approval=True,
                )
                structured_context = self._build_structured_context(user_input, mode, effort)
                async for ev in engine.run(
                    user_input,
                    context=structured_context,
                    strategy=strategy,
                    max_steps=max_steps,
                ):
                    if ev.type == "final_answer":
                        structured_final = ev.data
                    if ev.type == "error":
                        structured_final = None  # fall back below
                        break
                    yield ev
            except (RuntimeError, OSError, ImportError, ValueError) as exc:
                yield AgentEvent("error", f"Structured reasoning unavailable ({exc!s}); using standard loop.")
            else:
                if structured_final:
                    # The final answer event was already streamed above; also save
                    # it to the conversation so future turns have full context.
                    self.memory.add_message(session_id, "assistant", structured_final)
                    await self._finalize_run(
                        session_id, user_input, structured_final, mode, strategy, auto_commit
                    )
                    self._checkpoint_save(
                        session_id=session_id, user_input=user_input, mode=mode,
                        effort=effort, strategy=strategy, messages=messages,
                        steps_done=max_steps, status="done", final_answer=structured_final,
                    )
                    return
                yield AgentEvent("error", "Structured reasoning finished without a final answer; using standard loop.")
            # fall through to the standard loop below if structured failed

        # Deep Search mode: seed the context with an auto-researched dossier first
        if mode == "deep_search":
            yield AgentEvent("status", "Building deep search dossier...")
            try:
                from .deep_search import DeepSearchEngine
                dossier = await DeepSearchEngine().run(user_input)
                context_block = (
                    f"### DEEP SEARCH DOSSIER (auto-researched):\n"
                    f"Topic: {dossier['topic']}\n"
                    f"Total sources found: {dossier['total_sources_found']}\n\n"
                    "Sources:\n"
                )
                for s in dossier.get("sources", [])[:6]:
                    context_block += f"- {s.get('title', '')}: {s.get('url', '')}\n"
                messages.append({"role": "system", "content": context_block})
                yield AgentEvent("status", f"Dossier ready: {dossier['total_sources_found']} sources found.")
            except (RuntimeError, OSError, ImportError) as e:
                yield AgentEvent("status", f"Auto deep search unavailable: {e!s}")

        yield AgentEvent("status", f"Planning and analyzing the task... (effort: {effort}, max steps: {max_steps})")

        iteration = 0
        used_tools = False
        run_tools: list[str] = []
        reflect_done = False

        while iteration < max_steps:
            iteration += 1
            yield AgentEvent("step_start", {"step": iteration, "max_steps": max_steps})

            # Phase 10: keep the in-run window inside the configured budget
            # proactively (a no-op until the context actually exceeds it), so
            # long runs never fight the provider window one step too late.
            messages = trim_messages_for_context(messages)

            available_tools = self._build_tools_list()

            try:
                response, messages, chat_notes = await self._chat_with_recovery(
                    messages, available_tools
                )
            except (RuntimeError, OSError, aiohttp.ClientError) as e:
                err_msg = f"Error connecting to LLM: {e!s}"
                yield AgentEvent("error", err_msg)
                self._checkpoint_save(
                    session_id=session_id, user_input=user_input, mode=mode,
                    effort=effort, strategy=strategy, messages=messages,
                    steps_done=iteration, status="error",
                )
                return
            for note in chat_notes:
                yield AgentEvent("status", note)

            # Yield thoughts if any
            if response.thoughts:
                yield AgentEvent("thought", response.thoughts)

            # If model produced tool calls, execute them (in parallel)
            if response.tool_calls:
                used_tools = True
                used_names = [
                    str(tc.get("function", {}).get("name", "tool"))
                    for tc in response.tool_calls
                    if isinstance(tc, dict)
                ]
                run_tools.extend(used_names)
                async for ev in self._emit_tool_results(response, messages, iteration):
                    yield ev

                # Persist live state after each step (resume-safe)
                self._checkpoint_save(
                    session_id=session_id, user_input=user_input, mode=mode,
                    effort=effort, strategy=strategy, messages=messages,
                    steps_done=iteration, tools_used=used_names, status="running",
                )

                # Check if iterations limit reached
                if iteration >= max_steps:
                    yield AgentEvent("final_answer", f"Reached the maximum number of steps ({max_steps}). The latest state and results are preserved above.")
                    return
                continue

            # ---- No tool calls: candidate final answer ----
            final_text = response.content or ""

            # Reflection (critic) pass: after real tool use (or always in deep / high-effort runs)
            needs_reflection = used_tools or mode in ("deep", "deep_search") or effort in ("high", "ultra")
            if needs_reflection and not reflect_done:
                reflect_done = True
                yield AgentEvent("status", "Critically reviewing results (reflection)...")
                critic_messages = list(messages) + [
                    {"role": "assistant", "content": final_text},
                    {"role": "user", "content": REFLECTION_PROMPT}
                ]
                try:
                    crit = await self.llm.chat_completion(critic_messages, tools=available_tools)
                except (RuntimeError, OSError, aiohttp.ClientError) as e:
                    yield AgentEvent("error", f"Reflection pass error: {e!s}")
                    crit = None

                if crit is not None:
                    if crit.thoughts:
                        yield AgentEvent("thought", crit.thoughts)
                    if crit.tool_calls:
                        # Reflection decided more work is needed — execute it
                        async for ev in self._emit_tool_results(crit, messages, iteration):
                            yield ev
                        self._checkpoint_save(
                            session_id=session_id, user_input=user_input, mode=mode,
                            effort=effort, strategy=strategy, messages=messages,
                            steps_done=iteration, status="running",
                        )
                        if iteration >= max_steps:
                            yield AgentEvent("final_answer", f"Reached the maximum number of steps ({max_steps}). The latest state and results are preserved above.")
                            return
                        continue
                    elif crit.content:
                        # Reflection produced the polished final answer
                        final_text = crit.content or final_text

            yield AgentEvent("final_answer", final_text)
            await self._finalize_run(session_id, user_input, final_text, mode, strategy, auto_commit)
            self.memory.add_message(session_id, "assistant", final_text, thoughts=response.thoughts)
            self._checkpoint_save(
                session_id=session_id, user_input=user_input, mode=mode,
                effort=effort, strategy=strategy, messages=messages,
                steps_done=iteration, tools_used=run_tools,
                status="done", final_answer=final_text,
            )
            return