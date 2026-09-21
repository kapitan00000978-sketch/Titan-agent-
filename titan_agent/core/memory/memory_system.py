"""
Memory System - SQLite-backed episodic, semantic, procedural and working memory.

Implements MemGPT/Mem0-style patterns:
- Episodic: structured records of tasks/sessions with outcomes
- Semantic: consolidated facts with decay-aware retrieval
- Procedural: reusable how-to skills
- Working: ephemeral in-process context for the current task
- Consolidation: episodic -> semantic on repeated high-importance patterns
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .types import (
    ConsolidationResult,
    MemoryKind,
    MemoryQuery,
    MemoryRecord,
    MemoryStats,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return _now()


def _tokens(text: str) -> set[str]:
    """Naive keyword tokenization for retrieval scoring."""
    words = set()
    buffer = []
    for ch in text.lower():
        if ch.isalnum():
            buffer.append(ch)
        else:
            if buffer:
                words.add("".join(buffer))
                buffer = []
    if buffer:
        words.add("".join(buffer))
    return words


class MemorySystem:
    """Unified memory store with retrieval scoring and consolidation."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else Path.cwd() / "titan_core_memory.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._working: dict[str, MemoryRecord] = {}
        self._consolidations = 0
        self._init_db()

    # ---------- Internals ----------

    @contextmanager
    def _conn(self) -> Iterable[sqlite3.Connection]:
        """Context-managed connection: always closed (Windows file-lock safe)."""
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
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    meta TEXT NOT NULL DEFAULT '{}',
                    importance REAL NOT NULL DEFAULT 0.5,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'global'
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_kind ON memories(kind)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_scope ON memories(scope)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_created ON memories(created_at)"
            )

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=int(row["id"]),
            uid=row["uid"],
            kind=MemoryKind(row["kind"]),
            content=row["content"],
            metadata=json.loads(row["meta"] or "{}"),
            importance=float(row["importance"]),
            access_count=int(row["access_count"]),
            scope=row["scope"],
            created_at=_parse_iso(row["created_at"]),
            last_accessed=_parse_iso(row["last_accessed"]),
        )

    # ---------- Write ----------

    def remember(
        self,
        content: str,
        kind: MemoryKind = MemoryKind.SEMANTIC,
        importance: float = 0.5,
        scope: str = "global",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        """Persist a new memory record."""
        record = MemoryRecord(
            kind=kind,
            content=content,
            importance=min(1.0, max(0.0, importance)),
            scope=scope or "global",
            metadata=metadata or {},
        )
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO memories
                    (uid, kind, content, meta, importance, access_count,
                     created_at, last_accessed, scope)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.uid,
                    record.kind.value,
                    record.content,
                    json.dumps(record.metadata),
                    record.importance,
                    record.access_count,
                    _iso(record.created_at),
                    _iso(record.last_accessed),
                    record.scope,
                ),
            )
            record.id = int(cur.lastrowid)
        return record

    def remember_working(self, key: str, content: str, metadata: dict[str, Any] | None = None) -> MemoryRecord:
        """Store a working (ephemeral) memory record keyed by name."""
        record = MemoryRecord(
            kind=MemoryKind.WORKING,
            content=content,
            importance=0.8,
            scope="working",
            metadata=metadata or {},
        )
        self._working[key] = record
        return record

    def update_importance(self, record_id: int, importance: float) -> bool:
        """Adjust importance (memory strengthening)."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE memories SET importance = ? WHERE id = ?",
                (min(1.0, max(0.0, importance)), record_id),
            )
            return cur.rowcount > 0

    # ---------- Read ----------

    def recall(
        self,
        query: str = "",
        kinds: Iterable[MemoryKind] | None = None,
        limit: int = 5,
        scope: str | None = None,
        min_score: float = 0.0,
        min_importance: float = 0.0,
    ) -> list[MemoryRecord]:
        """Retrieve memories ranked by composite score."""
        mq = MemoryQuery(
            query=query,
            kinds=list(kinds) if kinds else None,
            limit=limit,
            scope=scope,
            min_score=min_score,
            min_importance=min_importance,
        )
        return self.query(mq)

    def query(self, mq: MemoryQuery) -> list[MemoryRecord]:
        q_tokens = _tokens(mq.query) if mq.query else set()
        now = _now()

        conditions = ["kind != 'working'"]
        params: list[Any] = []
        if mq.kinds:
            placeholders = ", ".join("?" for _ in mq.kinds)
            conditions.append(f"kind IN ({placeholders})")
            params.extend(k.value for k in mq.kinds)
        if mq.scope:
            conditions.append("scope = ?")
            params.append(mq.scope)
        if mq.min_importance > 0:
            conditions.append("importance >= ?")
            params.append(mq.min_importance)

        where = " AND ".join(conditions)
        params.append(mq.limit * 4)  # fetch extra, re-rank in Python
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM memories
                WHERE {where}
                ORDER BY last_accessed DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()

        records = [self._row_to_record(r) for r in rows]
        for rec in records:
            if q_tokens:
                content_tokens = _tokens(rec.content)
                # Also score metadata keys/values lightly
                meta_text = " ".join(str(v) for v in rec.metadata.values())
                meta_tokens = _tokens(meta_text)
                overlap = len(q_tokens & (content_tokens | meta_tokens)) / len(q_tokens)
            else:
                overlap = 1.0
            rec.compute_score(keyword_overlap=overlap, now=now)

        scored = [r for r in records if r.score >= mq.min_score]
        scored.sort(key=lambda r: r.score, reverse=True)
        top = scored[: mq.limit]

        # Track access for the returned memories
        if top:
            with self._conn() as conn:
                conn.executemany(
                    "UPDATE memories SET access_count = access_count + 1, "
                    "last_accessed = ? WHERE id = ?",
                    [(_iso(now), r.id) for r in top],
                )
        return top

    def get(self, record_id: int) -> MemoryRecord | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (record_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def get_working(self, key: str) -> MemoryRecord | None:
        return self._working.get(key)

    def list_working(self) -> list[MemoryRecord]:
        return list(self._working.values())

    def list_recent(
        self,
        kind: MemoryKind | None = None,
        scope: str | None = None,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        conditions = ["kind != 'working'"]
        params: list[Any] = []
        if kind:
            conditions.append("kind = ?")
            params.append(kind.value)
        if scope:
            conditions.append("scope = ?")
            params.append(scope)
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM memories
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    # ---------- Lifecycle ----------

    def forget(
        self,
        older_than_days: float = 30.0,
        kind: MemoryKind | None = None,
        min_importance: float = 0.0,
    ) -> int:
        """Delete old, low-importance memories. Returns count removed."""
        cutoff = _now() - __import__("datetime").timedelta(days=older_than_days)
        conditions = ["created_at < ?", "importance <= ?"]
        params: list[Any] = [_iso(cutoff), min_importance]
        if kind:
            conditions.append("kind = ?")
            params.append(kind.value)
        with self._conn() as conn:
            cur = conn.execute(
                f"DELETE FROM memories WHERE {' AND '.join(conditions)}",
                tuple(params),
            )
            return cur.rowcount

    def clear(self, kind: MemoryKind | None = None) -> int:
        with self._conn() as conn:
            if kind:
                cur = conn.execute(
                    "DELETE FROM memories WHERE kind = ?", (kind.value,)
                )
            else:
                cur = conn.execute(
                    "DELETE FROM memories WHERE kind != 'working'"
                )
            return cur.rowcount

    def stats(self) -> MemoryStats:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT kind, COUNT(*) as c FROM memories GROUP BY kind"
            ).fetchall()
            agg = conn.execute(
                "SELECT MIN(created_at) as old, MAX(created_at) as new, "
                "COUNT(*) as total FROM memories"
            ).fetchone()
        by_kind = {r["kind"]: int(r["c"]) for r in rows}
        return MemoryStats(
            total=int(agg["total"] or 0),
            by_kind=by_kind,
            oldest=_parse_iso(agg["old"]) if agg["old"] else None,
            newest=_parse_iso(agg["new"]) if agg["new"] else None,
            total_consolidations=self._consolidations,
        )

    # ---------- Consolidation (episodic -> semantic) ----------

    def consolidate(
        self,
        min_importance: float = 0.6,
        episodes_scope: str | None = None,
    ) -> ConsolidationResult:
        """
        Turn repeated high-value episodic memories into semantic facts.

        Strategy: group recent episodes by scope, extract a summary fact when
        the group has enough members OR the single episode is very important.
        """
        episodes = self.list_recent(
            kind=MemoryKind.EPISODIC, scope=episodes_scope, limit=100
        )
        result = ConsolidationResult()

        # Group by scope
        by_scope: dict[str, list[MemoryRecord]] = {}
        for ep in episodes:
            by_scope.setdefault(ep.scope, []).append(ep)

        for scope, group in by_scope.items():
            high_value = [e for e in group if e.importance >= min_importance]
            if not high_value:
                result.skipped += len(group)
                continue

            # Already a semantic fact for this scope? Skip duplicate.
            existing = self.list_recent(
                kind=MemoryKind.SEMANTIC, scope=scope, limit=50
            )
            existing_contents = {e.content for e in existing}

            summary = self._build_summary(high_value)
            result.episodes_processed += len(high_value)
            if summary and summary not in existing_contents:
                self.remember(
                    content=summary,
                    kind=MemoryKind.SEMANTIC,
                    importance=min(1.0, max(high_value, key=lambda e: e.importance).importance + 0.1),
                    scope=scope,
                    metadata={"consolidated": True, "source_count": len(high_value)},
                )
                self._consolidations += 1
                result.facts_created += 1
                result.details.append(f"[{scope}] {summary}")
            else:
                result.skipped += len(high_value)
        return result

    @staticmethod
    def _build_summary(records: list[MemoryRecord]) -> str:
        """Compress a group of episodes into one semantic fact."""
        if not records:
            return ""
        if len(records) == 1:
            return records[0].content
        # Concatenate distinctive parts (content, deduplicated)
        seen: set[str] = set()
        parts: list[str] = []
        for r in records:
            content = r.content.strip()
            if content and content not in seen:
                seen.add(content)
                parts.append(content)
            if len(parts) >= 5:
                break
        return " | ".join(parts)