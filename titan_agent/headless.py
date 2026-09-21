"""
Titan Agent — Headless / CI runner (Claude-Code-style non-interactive mode).

Runs a single task to completion without any interactive UI and returns the
final answer plus a structured event log. Exit code 0 means a final answer was
produced, 1 means it was not.

Usage (CLI):
    python -m titan_agent.headless "Refactor the login module" --strategy plan --mode deep
    python -m titan_agent.headless "Summarize ./src" --json

Programmatic:
    from titan_agent.headless import run_headless
    code, answer, events = run_headless("task", strategy="plan", agent=my_agent)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from .agent import TitanAgent
from .config import MCP_CONFIG_FILE, WORKSPACE_DIR
from .llm_client import LLMClient
from .mcp_client import MCPManager
from .memory import MemoryManager
from .skills import SkillRegistry
from .telegram import TelegramManager
from .tools import ToolRegistry

STRATEGIES = ("auto", "plan", "react", "tot")
MODES = ("fast", "deep", "deep_search")
EFFORTS = ("auto", "low", "medium", "high", "ultra")


def build_agent(
    provider: str | None = None,
    model: str | None = None,
    tools: ToolRegistry | None = None,
    tool_policy: Any | None = None,
) -> TitanAgent:
    """Construct the same global wiring the web server uses.

    ``tools`` overrides the terminal tool registry (used by subagent roles to
    filter capability) and ``tool_policy`` is the agent-level allowed/blocked
    tool set enforced in ``execute_tool_unified``.
    """
    llm = LLMClient(provider=provider, model=model) if provider else LLMClient()
    return TitanAgent(
        llm=llm,
        tools=tools or ToolRegistry(WORKSPACE_DIR),
        mcp=MCPManager(MCP_CONFIG_FILE),
        memory=MemoryManager(),
        skills=SkillRegistry(),
        telegram=TelegramManager(),
        tool_policy=tool_policy,
    )


async def _run_task(
    task: str,
    session_id: str,
    strategy: str,
    mode: str,
    effort: str,
    agent: TitanAgent | None,
    auto_commit: bool | None = None,
    resume: bool = False,
    system_extra: str | None = None,
) -> tuple[int, str, list[dict[str, Any]]]:
    the_agent = agent or build_agent()
    events: list[dict[str, Any]] = []
    final: str = ""
    errors: list[str] = []
    async for ev in the_agent.run_task(
        task,
        session_id=session_id,
        mode=mode,
        effort=effort,
        strategy=strategy,
        auto_commit=auto_commit,
        resume=resume,
        system_extra=system_extra,
    ):
        events.append(ev.to_dict())
        if ev.type == "final_answer":
            final = (final + "\n\n" + ev.data).strip() if final else ev.data
        elif ev.type == "error":
            errors.append(str(ev.data))
    code = 0 if final else 1
    return code, final, events


def run_headless(
    task: str,
    strategy: str = "auto",
    mode: str = "fast",
    effort: str = "auto",
    provider: str | None = None,
    model: str | None = None,
    session_id: str = "headless",
    agent: TitanAgent | None = None,
    auto_commit: bool | None = None,
    resume: bool | None = None,
    system_extra: str | None = None,
) -> tuple[int, str, list[dict[str, Any]]]:
    """Run a task to completion and return (exit_code, final_answer, events).

    ``system_extra`` is an optional system-prompt overlay appended for the run
    (used to give a subagent its role persona).
    """
    if strategy not in STRATEGIES:
        strategy = "auto"
    if mode not in MODES:
        mode = "fast"
    if effort not in EFFORTS:
        effort = "auto"
    if provider:
        agent = build_agent(provider, model)
    return asyncio.run(
        _run_task(task, session_id, strategy, mode, effort, agent, auto_commit, resume or False, system_extra)
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _safe_print(text: str) -> None:
    """Print UTF-8 safely even on legacy codepage terminals."""
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))
        sys.stdout.buffer.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="titan-headless",
        description="Titan Agent headless / CI runner — executes a task and exits.",
    )
    parser.add_argument("task", help="task to execute")
    parser.add_argument("--strategy", choices=STRATEGIES, default="auto",
                        help="structured reasoning strategy (auto/plan/react/tot)")
    parser.add_argument("--mode", choices=MODES, default="fast",
                        help="effort mode (fast/deep/deep_search)")
    parser.add_argument("--effort", choices=EFFORTS, default="auto",
                        help="iteration budget scaling")
    parser.add_argument("--provider", default=None, help="LLM provider override")
    parser.add_argument("--model", default=None, help="LLM model override")
    parser.add_argument("--session-id", default="headless")
    parser.add_argument("--json", action="store_true",
                        help="print a JSON document (exit_code, final_answer, events)")
    parser.add_argument("--auto-commit", action="store_true",
                        help="commit workspace changes after a successful run (Aider-style git-first)")
    parser.add_argument("--resume", action="store_true",
                        help="resume this session from its checkpoint (Devin/Claude-Code-style continuity)")
    args = parser.parse_args(argv)

    code, final, events = run_headless(
        args.task,
        strategy=args.strategy,
        mode=args.mode,
        effort=args.effort,
        provider=args.provider,
        model=args.model,
        session_id=args.session_id,
        auto_commit=True if args.auto_commit else None,
        resume=True if args.resume else None,
    )
    if args.json:
        _safe_print(
            json.dumps(
                {"exit_code": code, "final_answer": final, "events": events},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        _safe_print(final or "(no answer produced)")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))