"""Cron scheduler for TITAN AGENT (Hermes-class scheduled agent tasks).

Reads `cron/jobs.json` (same shape Hermes/ECC uses) and fires enabled jobs on
their schedule by invoking an async runner — in the server this is the Titan
agent itself, so a job is just a prompt executed autonomously on a timer.

Two schedule formats are supported per job:
    "interval_minutes": N          -> runs every N minutes
    "cron": "minute hour dom mon dow" -> standard 5-field cron (minute-first)

State (last_run / last_status / last_result) persists back into jobs.json so a
restart does not lose the history.
"""
import asyncio
import json
import os
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import BASE_DIR

DEFAULT_JOBS_FILE = BASE_DIR / "cron" / "jobs.json"

# How often the scheduler wakes to check for due jobs.
TICK_SECONDS = int(os.getenv("TITAN_CRON_TICK", "15"))


def _parse_cron(expr: str) -> dict[str, set[int] | None]:
    """Parse a 5-field cron expression into a per-field allowed-set dict."""
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError("cron must have 5 fields: minute hour dom month dow")
    fields = ["minute", "hour", "dom", "month", "dow"]
    parsed: dict[str, set[int] | None] = {}
    for name, part in zip(fields, parts):
        if part == "*":
            parsed[name] = None
        elif part.startswith("*/"):
            step = int(part[2:])
            if step <= 0:
                raise ValueError(f"Invalid step in cron field: {part}")
            parsed[name] = set(range(0, 60 if name == "minute" else 24, step))
        elif "," in part:
            parsed[name] = {int(x) for x in part.split(",") if x}
        elif "-" in part:
            lo, hi = (int(x) for x in part.split("-"))
            if hi < lo:
                raise ValueError(f"Invalid range in cron field: {part}")
            parsed[name] = set(range(lo, hi + 1))
        else:
            parsed[name] = {int(part)}
    return parsed


def _matches_cron(parsed: dict[str, set[int] | None], now: datetime) -> bool:
    """Check whether `now` matches the parsed cron fields."""
    if parsed["minute"] is not None and now.minute not in parsed["minute"]:
        return False
    if parsed["hour"] is not None and now.hour not in parsed["hour"]:
        return False
    if parsed["dom"] is not None and now.day not in parsed["dom"]:
        return False
    if parsed["month"] is not None and now.month not in parsed["month"]:
        return False
    if parsed["dow"] is not None:
        # cron: 0=Sunday ... 6=Saturday. datetime.weekday(): Monday=0 ... Sunday=6.
        py_dow = (now.weekday() + 1) % 7  # -> Sunday=0 ... Saturday=6
        if py_dow not in parsed["dow"]:
            return False
    return True


class CronScheduler:
    """Background task loop that runs due jobs with an async runner callable."""

    def __init__(
        self,
        runner: Callable[[str, str, str, str], Awaitable[str]],
        jobs_file: Path = DEFAULT_JOBS_FILE,
        tick_seconds: float = TICK_SECONDS,
    ):
        self.runner = runner  # async (prompt, session_id, mode, effort) -> str
        self.jobs_file = Path(jobs_file)
        self.tick_seconds = tick_seconds
        self.jobs: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._loop_task: asyncio.Task | None = None
        self._running: set[str] = set()
        self._cron_fired: set[str] = set()  # "job_id:YYYY-MM-DD HH:MM" dedupe
        self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    # ------------------------------------------------------------------ IO
    def _load(self):
        if self.jobs_file.exists():
            try:
                data = json.loads(self.jobs_file.read_text(encoding="utf-8"))
                self.jobs = {j["id"]: j for j in data.get("jobs", [])}
            except (OSError, json.JSONDecodeError):
                self.jobs = {}

    def _save(self):
        payload = {"jobs": list(self.jobs.values())}
        self.jobs_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ----------------------------------------------------------- CRUD API
    def list_jobs(self) -> list[dict[str, Any]]:
        out = []
        for job in self.jobs.values():
            item = dict(job)
            item["is_running"] = job["id"] in self._running
            out.append(item)
        return out

    def add_job(
        self,
        prompt: str,
        name: str = "cron job",
        schedule: dict[str, Any] | None = None,
        mode: str = "fast",
        effort: str = "auto",
        session_id: str = "",
        enabled: bool = True,
        job_id: str = "",
    ) -> dict[str, Any]:
        schedule = schedule or {"interval_minutes": 60}
        if "cron" in schedule and isinstance(schedule["cron"], str):
            _parse_cron(schedule["cron"])  # validate early, raises ValueError
        job_id = job_id or f"job_{int(time.time())}"
        job = {
            "id": job_id,
            "name": name,
            "prompt": prompt,
            "schedule": schedule,
            "mode": mode if mode in ("fast", "deep", "deep_search") else "fast",
            "effort": effort if effort in ("auto", "low", "medium", "high", "ultra") else "auto",
            "session_id": session_id or f"cron_{job_id}",
            "enabled": bool(enabled),
            "last_run": None,
            "last_status": None,
            "last_result": None,
        }
        self.jobs[job_id] = job
        self._save()
        return dict(job)

    def remove_job(self, job_id: str) -> bool:
        if job_id in self.jobs:
            del self.jobs[job_id]
            self._save()
            return True
        return False

    def toggle_job(self, job_id: str) -> dict[str, Any] | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        job["enabled"] = not job.get("enabled", True)
        self._save()
        return dict(job)

    # ----------------------------------------------------------- Execution
    def _is_due(self, job: dict[str, Any], now: datetime) -> bool:
        schedule = job.get("schedule") or {}
        last_run = job.get("last_run")
        if "interval_minutes" in schedule:
            interval = float(schedule["interval_minutes"])
            if last_run is None:
                return True
            return (time.time() - last_run) >= interval * 60
        if "cron" in schedule:
            try:
                parsed = _parse_cron(str(schedule["cron"]))
            except ValueError:
                return False
            if not _matches_cron(parsed, now):
                return False
            key = f"{job['id']}:{now:%Y-%m-%d %H:%M}"
            if key in self._cron_fired:
                return False
            self._cron_fired.add(key)
            if len(self._cron_fired) > 1000:
                self._cron_fired.clear()
            return True
        return False

    async def run_now(self, job_id: str) -> dict[str, Any]:
        """Force-run a job regardless of schedule (used by /run-now or tests)."""
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError(f"Unknown cron job: {job_id}")
        return await self._execute(job)

    async def _execute(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = job["id"]
        if job_id in self._running:
            return dict(job)
        self._running.add(job_id)
        started = time.time()
        job["last_run"] = started
        job["last_status"] = "running"
        try:
            result = await self.runner(
                job.get("prompt", ""),
                job.get("session_id", f"cron_{job_id}"),
                job.get("mode", "fast"),
                job.get("effort", "auto"),
            )
            job["last_status"] = "success"
            job["last_result"] = str(result)[:2000]
            job["last_duration_sec"] = round(time.time() - started, 2)
        except (RuntimeError, OSError, ValueError) as e:
            job["last_status"] = "error"
            job["last_result"] = f"ERROR: {e!s}"
            job["last_duration_sec"] = round(time.time() - started, 2)
        finally:
            self._running.discard(job_id)
            self._save()
        return dict(job)

    # ----------------------------------------------------------- Loop
    async def _tick(self):
        now = datetime.now(timezone.utc)
        for job in self.jobs.values():
            if not job.get("enabled", True):
                continue
            if job["id"] in self._running:
                continue
            if self._is_due(job, now):
                asyncio.create_task(self._execute(job))

    async def start(self):
        if self._loop_task is not None and not self._loop_task.done():
            return
        async def _loop():
            import logging
            log = logging.getLogger(__name__)
            while True:
                try:
                    await self._tick()
                except RuntimeError as e:
                    log.debug("Scheduler tick error: %s", e)
                await asyncio.sleep(self.tick_seconds)
        self._loop_task = asyncio.create_task(_loop())

    async def stop(self):
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except (asyncio.CancelledError, RuntimeError):
                pass
            self._loop_task = None
        # Wait for in-flight jobs to finish before exiting.
        while self._running:
            await asyncio.sleep(0.2)