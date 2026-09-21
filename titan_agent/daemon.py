"""
Phase 7 (Full Autonomy) — Autonomous Daemon Loop.

A self-running worker that claims tasks from the persistent :class:`TaskQueue`
and executes them to completion WITHOUT a human at the keyboard:

  python -m titan_agent.daemon            # run forever, polling the queue
  python -m titan_agent.daemon --once     # process all due tasks, then exit
  python -m titan_agent.daemon --poll 2   # poll every 2 seconds

Each task is executed through the headless runner in a worker thread (so the
event loop and the nested asyncio.run inside run_headless never conflict).
On failure the queue records the error and retries with backoff; the daemon
simply moves on to the next task — no human intervention needed.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Callable
from typing import Any

from . import headless
from .config import DAEMON_MAX_CONCURRENT, DAEMON_POLL_INTERVAL, TASK_QUEUE_FILE
from .queue import TaskQueue

log = logging.getLogger(__name__)

Runner = Callable[[str, dict[str, Any]], tuple[int, str, list[dict[str, Any]]]]


class TaskDaemon:
    """Autonomous worker loop over a persistent TaskQueue."""

    def __init__(
        self,
        queue: TaskQueue,
        runner: Runner | None = None,
        poll_interval: float = DAEMON_POLL_INTERVAL,
        max_concurrent: int = DAEMON_MAX_CONCURRENT,
    ):
        self.queue = queue
        self.runner = runner or self._default_runner
        self.poll_interval = max(0.5, float(poll_interval))
        self.max_concurrent = max(1, int(max_concurrent))
        self._stop = asyncio.Event()
        self._processed = 0

    @staticmethod
    def _default_runner(task: str, opts: dict[str, Any]) -> tuple[int, str, list[dict[str, Any]]]:
        """Execute one task via the headless runner (blocking; runs in a thread)."""
        return headless.run_headless(
            task,
            strategy=str(opts.get("strategy", "auto")),
            mode=str(opts.get("mode", "fast")),
            effort=str(opts.get("effort", "auto")),
            provider=opts.get("provider"),
            model=opts.get("model"),
            session_id=f"daemon-task-{opts.get('task_id', 'x')}",
        )

    async def _execute(self, task_id: int, task_text: str) -> None:
        """Claim-sensitive execution: run, record result/error, increment counter."""
        opts: dict[str, Any] = {"task_id": task_id}
        try:
            code, final, _events = await asyncio.to_thread(self.runner, task_text, opts)
        except Exception as exc:
            log.exception("task %s crashed", task_id)
            self.queue.fail(task_id, f"daemon crash: {exc}")
            return
        if code == 0:
            self.queue.complete(task_id, final or "Task completed (no final text).")
            log.info("task %s done", task_id)
        else:
            self.queue.fail(task_id, final or "Task failed without an error message.")
            log.warning("task %s failed", task_id)
        self._processed += 1

    async def run_once(self) -> int:
        """Process all currently-due tasks (up to max_concurrent at once). Return count."""
        while True:
            claimed = [
                self.queue.claim_next()
                for _ in range(self.max_concurrent)
            ]
            tasks = [t for t in claimed if t is not None]
            if not tasks:
                break
            await asyncio.gather(
                *(self._execute(t.id, t.task) for t in tasks)
            )
        return self._processed

    async def run_forever(self) -> int:
        """Poll the queue forever until stop() is called."""
        while not self._stop.is_set():
            try:
                await self.run_once()
            except Exception:
                log.exception("daemon poll cycle error")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                pass
        return self._processed

    def stop(self) -> None:
        self._stop.set()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="titan-daemon",
        description="Titan Agent autonomous task daemon — processes the persistent queue by itself.",
    )
    p.add_argument("--once", action="store_true", help="Process all due tasks, then exit.")
    p.add_argument("--poll", type=float, default=DAEMON_POLL_INTERVAL, help="Poll interval in seconds.")
    p.add_argument("--concurrency", type=int, default=DAEMON_MAX_CONCURRENT, help="Parallel task workers.")
    p.add_argument("--queue", default=str(TASK_QUEUE_FILE), help="SQLite queue file path.")
    p.add_argument("--list", action="store_true", help="List current queue contents and exit.")
    p.add_argument("--stats", action="store_true", help="Print queue stats and exit.")
    return p


def _print(text: str) -> None:
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", "replace"))
        sys.stdout.buffer.flush()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    with TaskQueue(args.queue) as q:
        if args.list:
            for t in q.list(limit=100):
                _print(
                    f"#{t.id} [{t.status}] prio={t.priority} attempts={t.attempts}/"
                    f"{t.max_attempts} :: {t.name}"
                )
            return 0
        if args.stats:
            _print(f"Queue stats: {q.stats()}")
            return 0

        daemon = TaskDaemon(
            q,
            poll_interval=args.poll,
            max_concurrent=args.concurrency,
        )

        async def _run() -> int:
            if args.once:
                return await daemon.run_once()
            return await daemon.run_forever()

        try:
            processed = asyncio.run(_run())
        except KeyboardInterrupt:
            _print("\nDaemon stopped by user.")
            return 0
        _print(f"Processed {processed} task(s).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())