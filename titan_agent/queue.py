"""
Phase 7 (Full Autonomy) — Persistent Task Queue.

A tiny SQLite-backed queue so Titan can accept and process many tasks on its
own, without a human at the keyboard: tasks are enqueued (by a user, another
agent, a cron job or a webhook), claimed one at a time by the daemon, run to
completion and marked done — or retried with backoff on failure.

Zero dependencies (stdlib sqlite3). Thread-safe via a global lock so the same
queue can be shared between the web server and the daemon loop.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    task        TEXT NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending|running|done|failed|cancelled
    attempts    INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    schedule_at REAL NOT NULL DEFAULT 0,           -- epoch seconds; 0 = run now
    created_at  REAL NOT NULL,
    started_at  REAL,
    finished_at REAL,
    result      TEXT,
    error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
"""

PENDING = "pending"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"
STATUSES = (PENDING, RUNNING, DONE, FAILED, CANCELLED)

MAX_RETRY_BACKOFF_SECONDS = 60.0


@dataclass
class Task:
    """One queued unit of work."""

    id: int
    name: str
    task: str
    priority: int = 0
    status: str = PENDING
    attempts: int = 0
    max_attempts: int = 3
    schedule_at: float = 0.0
    created_at: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None
    result: str | None = None
    error: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Task:
        return cls(
            id=row["id"],
            name=row["name"],
            task=row["task"],
            priority=row["priority"],
            status=row["status"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            schedule_at=row["schedule_at"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            result=row["result"],
            error=row["error"],
        )

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "name": self.name,
            "task": self.task,
            "priority": self.priority,
            "status": self.status,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "schedule_at": self.schedule_at or None,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
        }
        try:
            d["result_parsed"] = json.loads(self.result) if self.result else None
        except (json.JSONDecodeError, TypeError):
            d["result_parsed"] = None
        return d


class TaskQueue:
    """Persistent, thread-safe task queue backed by SQLite."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ---- lifecycle -------------------------------------------------------

    def enqueue(
        self,
        task: str,
        name: str | None = None,
        priority: int = 0,
        schedule_at: float = 0.0,
        max_attempts: int = 3,
    ) -> int:
        """Add a task. Returns its id. schedule_at is epoch seconds (0 = now)."""
        t = time.time()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO tasks (name, task, priority, schedule_at, created_at, max_attempts)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (name or task[:60], task, int(priority), float(schedule_at or 0), t, max(1, int(max_attempts))),
            )
            self._conn.commit()
            last_id = cur.lastrowid
            if last_id is None:  # pragma: no cover - sqlite sets it for INSERT
                raise RuntimeError("Task insert did not return a row id")
            return int(last_id)

    def claim_next(self, now: float | None = None) -> Task | None:
        """Atomically claim the highest-priority task that is due, or None.

        A task is due when it is 'pending' and schedule_at <= now. Claimed tasks
        move to 'running' so only one worker processes them.
        """
        now = time.time() if now is None else float(now)
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tasks WHERE status = ? AND schedule_at <= ?"
                " ORDER BY priority DESC, created_at ASC LIMIT 1",
                (PENDING, now),
            ).fetchone()
            if row is None:
                return None
            self._conn.execute(
                "UPDATE tasks SET status = ?, started_at = ? WHERE id = ?",
                (RUNNING, time.time(), row["id"]),
            )
            self._conn.commit()
            return Task.from_row(
                self._conn.execute("SELECT * FROM tasks WHERE id = ?", (row["id"],)).fetchone()
            )

    def complete(self, task_id: int, result: str | dict | None = None) -> bool:
        """Mark a running/pending task as done with an optional result."""
        if isinstance(result, dict):
            result = json.dumps(result, ensure_ascii=False)
        with self._lock:
            cur = self._conn.execute(
                "UPDATE tasks SET status = ?, result = ?, finished_at = ? WHERE id = ?",
                (DONE, result, time.time(), int(task_id)),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def fail(self, task_id: int, error: str) -> bool:
        """Record a failure; retry with backoff if attempts remain, else mark failed."""
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT attempts, max_attempts FROM tasks WHERE id = ?", (int(task_id),)
            ).fetchone()
            if row is None:
                return False
            attempts = int(row["attempts"]) + 1
            if attempts >= int(row["max_attempts"]):
                self._conn.execute(
                    "UPDATE tasks SET status = ?, attempts = ?, error = ?, finished_at = ? WHERE id = ?",
                    (FAILED, attempts, str(error)[:4000], now, int(task_id)),
                )
            else:
                # Exponential-ish backoff: 5s, 15s, 30s, capped at 60s.
                backoff = min(5.0 * (2 ** max(0, attempts - 1)), MAX_RETRY_BACKOFF_SECONDS)
                self._conn.execute(
                    "UPDATE tasks SET status = ?, attempts = ?, error = ?,"
                    " schedule_at = ?, started_at = NULL WHERE id = ?",
                    (PENDING, attempts, str(error)[:4000], now + backoff, int(task_id)),
                )
            self._conn.commit()
            return True

    def cancel(self, task_id: int) -> bool:
        """Cancel a pending task (running tasks are left to finish)."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE tasks SET status = ? WHERE id = ? AND status = ?",
                (CANCELLED, int(task_id), PENDING),
            )
            self._conn.commit()
            return cur.rowcount > 0

    # ---- queries ---------------------------------------------------------

    def get(self, task_id: int) -> Task | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (int(task_id),)).fetchone()
        return Task.from_row(row) if row else None

    def list(self, status: str | None = None, limit: int = 50) -> list[Task]:
        limit = max(1, min(int(limit or 50), 500))
        q = "SELECT * FROM tasks"
        args: list[Any] = []
        if status:
            q += " WHERE status = ?"
            args.append(status)
        q += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        return [Task.from_row(r) for r in rows]

    def stats(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT status, COUNT(*) AS c FROM tasks GROUP BY status"
            ).fetchall()
        return {r["status"]: int(r["c"]) for r in rows}

    def clear(self, status: str | None = None) -> int:
        """Delete tasks, optionally only those in one status. Returns count deleted."""
        with self._lock:
            if status:
                cur = self._conn.execute("DELETE FROM tasks WHERE status = ?", (status,))
            else:
                cur = self._conn.execute("DELETE FROM tasks")
            self._conn.commit()
            return cur.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()