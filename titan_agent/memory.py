import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from .config import BASE_DIR

DB_PATH = BASE_DIR / "titan_memory.db"

def _tokens(text: str) -> set[str]:
    """Lowercase alphanumeric tokens for lightweight relevance matching."""
    return set(re.findall(r"[a-z0-9][a-z0-9_\-']*", str(text).lower()))

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

    def remember_fact(self, key: str, value: str, category: str = "general"):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO knowledge (category, key, value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """, (category, key, value, time.time()))
            conn.commit()

    def search_knowledge(self, query: str, limit: int = 5) -> list[dict[str, str]]:
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
        starts the turn already knowing the user.
        """
        q_tokens = _tokens(query) if query else set()
        if not q_tokens:
            return []
        facts = self.get_all_knowledge()
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
