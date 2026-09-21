import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

from .config import BASE_DIR

DB_PATH = BASE_DIR / "titan_memory.db"

# Hermes "Memory Vault" scopes: global (across everything), project (per repo),
# team (shared with the team) and user (personal). The agent can write to any
# scope and search scoped or across all scopes.
VALID_SCOPES = ("global", "project", "team", "user")

def _tokens(text: str) -> set[str]:
    """Lowercase alphanumeric tokens for lightweight relevance matching."""
    return set(re.findall(r"[a-z0-9][a-z0-9_\-']*", str(text).lower()))


def _normalize_scope(scope: Optional[str]) -> str:
    s = (scope or "global").strip().lower()
    return s if s in VALID_SCOPES else "global"


class MemoryManager:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    thoughts TEXT,
                    tool_calls TEXT,
                    timestamp REAL
                )
            """)
            # Long term knowledge / memories
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT,
                    key TEXT UNIQUE,
                    value TEXT,
                    updated_at REAL
                )
            """)
            # Memory Vault: scoped long-term memory (global/project/team/user).
            # Primary key is (scope, key) so the same key can exist in many scopes.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vault (
                    scope TEXT NOT NULL DEFAULT 'global',
                    key TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    value TEXT,
                    updated_at REAL,
                    PRIMARY KEY (scope, key)
                )
            """)
            # Handoffs: agent-to-agent or agent-to-human pass-along notes
            # (Hermes "handoff" file pattern, persisted and queryable).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS handoffs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT DEFAULT 'global',
                    title TEXT,
                    content TEXT,
                    status TEXT DEFAULT 'open',
                    created_at REAL,
                    resolved_at REAL
                )
            """)
            conn.commit()

    def add_message(self, session_id: str, role: str, content: str, thoughts: str = "", tool_calls: list[dict[str, Any]] | None = None):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (session_id, role, content, thoughts, tool_calls, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                role,
                content,
                thoughts,
                json.dumps(tool_calls) if tool_calls else "[]",
                time.time()
            ))
            conn.commit()

    def get_recent_messages(self, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content, thoughts, tool_calls FROM messages
                WHERE session_id = ?
                ORDER BY id DESC LIMIT ?
            """, (session_id, limit))
            rows = cursor.fetchall()
            messages = []
            for r in reversed(rows):
                item = {"role": r[0], "content": r[1]}
                if r[2]:
                    item["thoughts"] = r[2]
                if r[3] and r[3] != "[]":
                    item["tool_calls"] = json.loads(r[3])
                messages.append(item)
            return messages

    # ------------------------------------------------------------ Knowledge
    def remember_fact(self, key: str, value: str, category: str = "general", scope: Optional[str] = None):
        if scope:
            # Scoped Memory Vault write (e.g. project/team/user)
            self.vault_remember(scope, key, value, category)
            return
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO knowledge (category, key, value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """, (category, key, value, time.time()))
            conn.commit()

    def search_knowledge(self, query: str, limit: int = 5, scope: Optional[str] = None) -> list[dict[str, str]]:
        if scope:
            return self.vault_search(query, limit=limit, scope=scope)
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category, key, value FROM knowledge
                WHERE key LIKE ? OR value LIKE ?
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit))
            return [{"category": r[0], "key": r[1], "value": r[2]} for r in cursor.fetchall()]

    def get_all_knowledge(self) -> list[dict[str, str]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT category, key, value FROM knowledge ORDER BY id DESC LIMIT 50")
            return [{"category": r[0], "key": r[1], "value": r[2]} for r in cursor.fetchall()]

    def recall_relevant(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        """Return the long-term facts most relevant to `query` (lexical overlap).

        Used to auto-seed a session with remembered context (Memory Agent
        pattern): the agent's message is matched against every saved fact and
        the best-scoring ones are injected into the system context so the model
        starts the turn already knowing the user. Merges legacy knowledge with
        Memory Vault scoped facts.
        """
        q_tokens = _tokens(query) if query else set()
        if not q_tokens:
            return []
        facts = self.get_all_knowledge() + self.vault_list(limit=200)
        ranked = []
        for f in facts:
            haystack = _tokens(f"{f['key']} {f['value']} {f['category']}")
            if not haystack:
                continue
            hits = len(q_tokens & haystack)
            if hits:
                # Prefer exact key matches and higher overlap share.
                key_hit = 1.0 if (q_tokens & _tokens(f["key"])) else 0.0
                ranked.append((hits + key_hit, len(haystack), f))
        ranked.sort(key=lambda r: (-r[0], r[1]))
        return [f for _, _, f in ranked[:limit]]

    def clear_session(self, session_id: str):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.commit()

    # ------------------------------------------------ Memory Vault (scoped)
    def vault_remember(self, scope: str, key: str, value: str, category: str = "general"):
        scope = _normalize_scope(scope)
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vault (scope, key, category, value, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(scope, key) DO UPDATE SET
                    category=excluded.category, value=excluded.value, updated_at=excluded.updated_at
            """, (scope, key, category, value, time.time()))
            conn.commit()

    def vault_search(self, query: str, limit: int = 5, scope: Optional[str] = None) -> list[dict[str, str]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if scope:
                cursor.execute("""
                    SELECT scope, category, key, value FROM vault
                    WHERE scope = ? AND (key LIKE ? OR value LIKE ?)
                    ORDER BY updated_at DESC LIMIT ?
                """, (_normalize_scope(scope), f"%{query}%", f"%{query}%", limit))
            else:
                cursor.execute("""
                    SELECT scope, category, key, value FROM vault
                    WHERE key LIKE ? OR value LIKE ?
                    ORDER BY updated_at DESC LIMIT ?
                """, (f"%{query}%", f"%{query}%", limit))
            return [{"scope": r[0], "category": r[1], "key": r[2], "value": r[3]} for r in cursor.fetchall()]

    def vault_list(self, scope: Optional[str] = None, limit: int = 100) -> list[dict[str, str]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if scope:
                cursor.execute(
                    "SELECT scope, category, key, value FROM vault WHERE scope = ? ORDER BY updated_at DESC LIMIT ?",
                    (_normalize_scope(scope), limit))
            else:
                cursor.execute(
                    "SELECT scope, category, key, value FROM vault ORDER BY updated_at DESC LIMIT ?", (limit,))
            return [{"scope": r[0], "category": r[1], "key": r[2], "value": r[3]} for r in cursor.fetchall()]

    # ----------------------------------------------------------- Handoffs
    def create_handoff(self, title: str, content: str, scope: str = "global") -> int:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO handoffs (scope, title, content, status, created_at)
                VALUES (?, ?, ?, 'open', ?)
            """, (_normalize_scope(scope), title, content, time.time()))
            conn.commit()
            return cursor.lastrowid

    def list_handoffs(self, status: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                    SELECT id, scope, title, content, status, created_at, resolved_at
                    FROM handoffs WHERE status = ? ORDER BY created_at DESC LIMIT ?
                """, (status, limit))
            else:
                cursor.execute("""
                    SELECT id, scope, title, content, status, created_at, resolved_at
                    FROM handoffs ORDER BY created_at DESC LIMIT ?
                """, (limit,))
            return [{
                "id": r[0], "scope": r[1], "title": r[2], "content": r[3],
                "status": r[4], "created_at": r[5], "resolved_at": r[6],
            } for r in cursor.fetchall()]

    def resolve_handoff(self, handoff_id: int, status: str = "resolved") -> bool:
        if status not in ("resolved", "cancelled"):
            status = "resolved"
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE handoffs SET status = ?, resolved_at = ? WHERE id = ?",
                (status, time.time(), handoff_id))
            conn.commit()
            return cursor.rowcount > 0