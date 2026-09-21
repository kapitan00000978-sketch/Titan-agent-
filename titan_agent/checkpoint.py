"""Phase 5 — Devin-style session checkpoints and resume.

A checkpoint captures a run's live state (conversation messages + metadata) so an
interrupted or long-running session can be resumed later — the same continuity
Devin's long-horizon sessions and Claude Code's ``--continue`` rely on.

Design rules:

- **Always-on by default**: the agent persists a checkpoint at run start, after
  every tool step, and on completion/error — an interruption never loses the
  session's work.
- **SQLite-backed and file-lock safe**: every connection is context-managed and
  closed, so the DB file is deletable even on Windows.
- **Resume** restores the last N messages and continues the classic loop from
  exactly where it stopped; a ``status == \"done\"`` session returns its saved
  final answer instead of re-running.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_MESSAGES = 40  # messages persisted per checkpoint (kept when resuming)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@dataclass
class RunCheckpoint:
    """Serializable snapshot of a run's live state."""

    session_id: str
    user_input: str
    mode: str = "fast"
    effort: str = "auto"
    strategy: str = "auto"
    messages: list[dict[str, Any]] = field(default_factory=list)
    steps_done: int = 0
    tools_used: list[str] = field(default_factory=list)
    status: str = "running"  # running | done | error
    final_answer: str | None = None
    created_at: str = ""
    updated_at: str = ""


class CheckpointStore:
    """SQLite store for run checkpoints (one row per session_id)."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else Path.cwd() / "titan_checkpoints.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    session_id TEXT PRIMARY KEY,
                    user_input TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'fast',
                    effort TEXT NOT NULL DEFAULT 'auto',
                    strategy TEXT NOT NULL DEFAULT 'auto',
                    messages TEXT NOT NULL DEFAULT '[]',
                    steps_done INTEGER NOT NULL DEFAULT 0,
                    tools_used TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'running',
                    final_answer TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    # ---------- persistence ----------

    def save(self, cp: RunCheckpoint) -> None:
        """Upsert a checkpoint (replaces any existing one for the session)."""
        now = _now()
        created = cp.created_at or now
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO checkpoints
                    (session_id, user_input, mode, effort, strategy, messages,
                     steps_done, tools_used, status, final_answer, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    user_input=excluded.user_input,
                    mode=excluded.mode,
                    effort=excluded.effort,
                    strategy=excluded.strategy,
                    messages=excluded.messages,
                    steps_done=excluded.steps_done,
                    tools_used=excluded.tools_used,
                    status=excluded.status,
                    final_answer=excluded.final_answer,
                    updated_at=excluded.updated_at
                """,
                (
                    cp.session_id,
                    cp.user_input[:2000],
                    cp.mode,
                    cp.effort,
                    cp.strategy,
                    json.dumps(cp.messages, ensure_ascii=False),
                    int(cp.steps_done),
                    json.dumps(cp.tools_used, ensure_ascii=False),
                    cp.status,
                    cp.final_answer[:4000] if cp.final_answer else None,
                    created,
                    now,
                ),
            )

    def load(self, session_id: str) -> RunCheckpoint | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE session_id = ?", (session_id,)
            ).fetchone()
        return self._row_to_cp(row) if row else None

    def list(self, limit: int = 20) -> list[RunCheckpoint]:
        """Recent checkpoints, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM checkpoints ORDER BY updated_at DESC, rowid DESC LIMIT ?",
                (max(1, min(500, int(limit))),),
            ).fetchall()
        return [self._row_to_cp(r) for r in rows]

    def delete(self, session_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM checkpoints WHERE session_id = ?", (session_id,))
        return cur.rowcount > 0

    def stats(self) -> dict[str, int]:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
            done = conn.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE status = 'done'"
            ).fetchone()[0]
        return {"total": int(total), "done": int(done)}

    # ---------- helpers ----------

    @staticmethod
    def _row_to_cp(row: sqlite3.Row) -> RunCheckpoint:
        try:
            messages = json.loads(row["messages"] or "[]")
        except (ValueError, TypeError):
            messages = []
        try:
            tools = json.loads(row["tools_used"] or "[]")
        except (ValueError, TypeError):
            tools = []
        return RunCheckpoint(
            session_id=row["session_id"],
            user_input=row["user_input"] or "",
            mode=row["mode"] or "fast",
            effort=row["effort"] or "auto",
            strategy=row["strategy"] or "auto",
            messages=messages if isinstance(messages, list) else [],
            steps_done=int(row["steps_done"] or 0),
            tools_used=tools if isinstance(tools, list) else [],
            status=row["status"] or "running",
            final_answer=row["final_answer"],
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )