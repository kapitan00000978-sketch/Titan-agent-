"""
Episodic Memory & Experience Replay Engine.

Maintains a persistent episodic experience database of past errors, root causes,
and verified resolutions. When the agent encounters a known error pattern, it instantly
retrieves the proven fix rather than exploring blindly.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _extract_error_fingerprint(error_text: str) -> tuple[str, str]:
    """
    Extracts normalized error type and invariant keywords from tracebacks.
    Returns (error_type, normalized_fingerprint).
    """
    cleaned = error_text.strip()
    # Try finding Python exception pattern: "NameError: name 'Path' is not defined"
    match = re.search(r"([A-Z][a-zA-Z0-9_]*(?:Error|Exception|Warning|Fault)):\s*(.+)", cleaned)
    if match:
        err_type = match.group(1)
        err_msg = match.group(2).strip()
    else:
        err_type = "GenericExecutionError"
        err_msg = cleaned[:120]

    # Normalize paths, timestamps, line numbers, and hex addresses
    norm = re.sub(r"line\s+\d+", "line <N>", err_msg)
    norm = re.sub(r"0x[0-9a-fA-F]+", "0x<HEX>", norm)
    norm = re.sub(r"['\"][^'\"]*[\/\\][^'\"]*['\"]", "<PATH>", norm)
    norm_fingerprint = f"{err_type}:{norm.lower().strip()}"
    return err_type, norm_fingerprint


@dataclass
class ExperienceEpisode:
    id: int
    error_type: str
    fingerprint: str
    raw_error: str
    diagnosis: str
    resolution: str
    success_count: int
    created_at: float
    updated_at: float

    def format_hint(self) -> str:
        return (
            f"### 💡 EPISODIC EXPERIENCE MATCH (Verified Past Solution):\n"
            f"- **Recognized Error**: `{self.error_type}`\n"
            f"- **Diagnosis**: {self.diagnosis or 'Previous known defect'}\n"
            f"- **Proven Resolution Recipe (Used successfully {self.success_count}x)**:\n"
            f"```\n{self.resolution}\n```\n"
            f"Apply this proven fix immediately to resolve the issue."
        )


class ExperienceReplayEngine:
    """Manages recording and instant recall of past error-fix episodes."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else Path("experience_replay.db")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS experience_episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT NOT NULL UNIQUE,
                    error_type TEXT NOT NULL,
                    raw_error TEXT NOT NULL,
                    diagnosis TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    success_count INTEGER DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exp_fp ON experience_episodes(fingerprint)")
            conn.commit()

    def record_experience(
        self,
        error_text: str,
        resolution: str,
        diagnosis: str = "",
        error_type: str = "",
    ) -> ExperienceEpisode:
        """Stores or increments success count of a verified error resolution."""
        derived_type, fp = _extract_error_fingerprint(error_text)
        final_type = error_type or derived_type
        now = time.time()

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id, success_count FROM experience_episodes WHERE fingerprint = ?",
                (fp,),
            ).fetchone()

            if row:
                conn.execute(
                    """
                    UPDATE experience_episodes
                    SET success_count = success_count + 1,
                        resolution = ?,
                        diagnosis = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (resolution, diagnosis or "Updated verified recipe", now, row["id"]),
                )
                conn.commit()
                ep_id = row["id"]
                count = row["success_count"] + 1
            else:
                cur = conn.execute(
                    """
                    INSERT INTO experience_episodes (
                        fingerprint, error_type, raw_error, diagnosis, resolution,
                        success_count, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (fp, final_type, error_text[:500], diagnosis, resolution, now, now),
                )
                conn.commit()
                ep_id = cur.lastrowid or 0
                count = 1

        return ExperienceEpisode(
            id=ep_id,
            error_type=final_type,
            fingerprint=fp,
            raw_error=error_text,
            diagnosis=diagnosis,
            resolution=resolution,
            success_count=count,
            created_at=now,
            updated_at=now,
        )

    def query_experience(self, error_text: str) -> ExperienceEpisode | None:
        """Finds proven past resolution for the incoming error."""
        if not error_text or len(error_text.strip()) < 5:
            return None

        _, fp = _extract_error_fingerprint(error_text)

        with self._get_connection() as conn:
            # 1. Exact fingerprint match
            row = conn.execute(
                "SELECT * FROM experience_episodes WHERE fingerprint = ?",
                (fp,),
            ).fetchone()

            if row:
                return ExperienceEpisode(
                    id=row["id"],
                    error_type=row["error_type"],
                    fingerprint=row["fingerprint"],
                    raw_error=row["raw_error"],
                    diagnosis=row["diagnosis"],
                    resolution=row["resolution"],
                    success_count=row["success_count"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

            # 2. Substring matching if exact match not found
            derived_type, _ = _extract_error_fingerprint(error_text)
            candidates = conn.execute(
                "SELECT * FROM experience_episodes WHERE error_type = ? ORDER BY success_count DESC LIMIT 10",
                (derived_type,),
            ).fetchall()

            for cand in candidates:
                # If key tokens from raw_error are in incoming error
                cand_raw = cand["raw_error"].lower()
                tokens = [t for t in cand_raw.split() if len(t) > 3][:6]
                if tokens and any(t in error_text.lower() for t in tokens):
                    return ExperienceEpisode(
                        id=cand["id"],
                        error_type=cand["error_type"],
                        fingerprint=cand["fingerprint"],
                        raw_error=cand["raw_error"],
                        diagnosis=cand["diagnosis"],
                        resolution=cand["resolution"],
                        success_count=cand["success_count"],
                        created_at=cand["created_at"],
                        updated_at=cand["updated_at"],
                    )

        return None

    def list_episodes(self, limit: int = 50) -> list[dict[str, Any]]:
        """Returns catalog of learned episodes."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT id, error_type, fingerprint, diagnosis, resolution, success_count, created_at FROM experience_episodes ORDER BY success_count DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
