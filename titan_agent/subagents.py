"""
Phase 7 (Full Autonomy) — Deep Subagent Architecture.

A supervisor-style subagent layer: a parent Titan can delegate sub-problems to
independent child agents and collect their results. Each subagent runs the
headless runner with its OWN session id and checkpoint namespace, so large
tasks decompose into isolated, verifiable units of work instead of one
monolithic run.

Design notes
------------
- Subagents execute synchronously in worker threads (unlike the daemon, the
  parent agent needs the RESULT before it can continue), so `delegate`/`team`
  are async functions that gather via asyncio.to_thread.
- Parallelism is bounded by max_workers (default 2) so the parent's LLM budget
  isn't thrashed by 20 simultaneous children.
- Each child gets a fresh session id (`sub-<parent_session>-<n>`) so
  checkpoints/memories never collide.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import headless

Runner = Callable[[str, dict[str, Any]], tuple[int, str, list[dict[str, Any]]]]


@dataclass
class SubagentResult:
    """Outcome of one delegated sub-task."""

    label: str
    exit_code: int
    final: str
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_text(self) -> str:
        if self.error:
            return f"### SUBAGENT [{self.label}] — ERROR\n{self.error}"
        status = "ok" if self.exit_code == 0 else f"FAILED (exit {self.exit_code})"
        return f"### SUBAGENT [{self.label}] — {status}\n{self.final}"


class SubagentPool:
    """Runs independent sub-task agents and collects their answers."""

    def __init__(
        self,
        runner: Runner | None = None,
        max_workers: int = 2,
    ):
        self.runner = runner or self._default_runner
        self.max_workers = max(1, int(max_workers))

    @staticmethod
    def _default_runner(task: str, opts: dict[str, Any]) -> tuple[int, str, list[dict[str, Any]]]:
        return headless.run_headless(
            task,
            strategy=str(opts.get("strategy", "auto")),
            mode=str(opts.get("mode", "fast")),
            effort=str(opts.get("effort", "auto")),
            provider=opts.get("provider"),
            model=opts.get("model"),
            session_id=str(opts.get("session_id", "subagent")),
        )

    async def delegate(
        self,
        task: str,
        session_id: str = "default_session",
        label: str = "worker",
        opts: dict[str, Any] | None = None,
    ) -> SubagentResult:
        """Run one sub-task and return its result (blocking until done)."""
        o: dict[str, Any] = dict(opts or {})
        o.setdefault("session_id", f"sub-{session_id}-{label}")
        try:
            code, final, events = await asyncio.to_thread(self.runner, task, o)
        except Exception as exc:  # noqa: BLE001 - report, don't crash the parent
            return SubagentResult(label=label, exit_code=1, final="", error=f"{exc}")
        return SubagentResult(label=label, exit_code=code, final=final, events=events)

    async def team(
        self,
        tasks: list[str],
        session_id: str = "default_session",
        labels: list[str] | None = None,
        opts: dict[str, Any] | None = None,
    ) -> list[SubagentResult]:
        """Run several independent sub-tasks in parallel, bounded by max_workers."""
        if not tasks:
            return []
        labels = labels or [f"worker-{i}" for i in range(1, len(tasks) + 1)]
        if len(labels) < len(tasks):
            labels = labels + [f"worker-{i}" for i in range(len(labels) + 1, len(tasks) + 1)]

        sem = asyncio.Semaphore(self.max_workers)

        async def one(task: str, label: str) -> SubagentResult:
            async with sem:
                return await self.delegate(task, session_id=session_id, label=label, opts=opts)

        return await asyncio.gather(*(one(t, l) for t, l in zip(tasks, labels)))