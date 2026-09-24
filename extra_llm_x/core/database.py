"""SQLite Storage Engine for Extra LLM X.

Manages persistent storage for generated API keys, rate limit quotas,
request analytics, and dynamically configured provider credentials.
"""
import sqlite3
import time
from typing import Any, Dict, List, Optional
from pathlib import Path
from .config import DB_PATH


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        """Create necessary tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # API Keys Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    key_prefix TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_used_at REAL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    rate_limit_rpm INTEGER DEFAULT 0,
                    quota_tokens INTEGER DEFAULT 0,
                    used_tokens INTEGER DEFAULT 0,
                    total_requests INTEGER DEFAULT 0
                )
            """)
            # Request Telemetry Logs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    key_id TEXT,
                    requested_model TEXT NOT NULL,
                    routed_provider TEXT NOT NULL,
                    routed_model TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    tokens_in INTEGER DEFAULT 0,
                    tokens_out INTEGER DEFAULT 0,
                    status_code INTEGER NOT NULL,
                    error_message TEXT
                )
            """)
            # Dynamic Provider Credentials Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS provider_credentials (
                    provider_id TEXT PRIMARY KEY,
                    api_key TEXT,
                    base_url TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    updated_at REAL NOT NULL
                )
            """)
            conn.commit()

    # --- API Key Management ---
    def insert_key(
        self,
        key_id: str,
        name: str,
        key_hash: str,
        key_prefix: str,
        rate_limit_rpm: int = 0,
        quota_tokens: int = 0
    ) -> Dict[str, Any]:
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO api_keys (id, name, key_hash, key_prefix, created_at, is_active, rate_limit_rpm, quota_tokens, used_tokens, total_requests)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, 0, 0)
            """, (key_id, name, key_hash, key_prefix, now, rate_limit_rpm, quota_tokens))
            conn.commit()
        return self.get_key_by_id(key_id)

    def get_key_by_hash(self, key_hash: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1", (key_hash,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_key_by_id(self, key_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_keys(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, key_prefix, created_at, last_used_at, is_active, rate_limit_rpm, quota_tokens, used_tokens, total_requests FROM api_keys ORDER BY created_at DESC")
            return [dict(r) for r in cursor.fetchall()]

    def revoke_key(self, key_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,))
            conn.commit()
            return cursor.rowcount > 0

    def record_key_usage(self, key_id: str, tokens: int) -> None:
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE api_keys 
                SET total_requests = total_requests + 1,
                    used_tokens = used_tokens + ?,
                    last_used_at = ?
                WHERE id = ?
            """, (tokens, now, key_id))
            conn.commit()

    # --- Telemetry Logs & Analytics ---
    def log_request(
        self,
        key_id: Optional[str],
        requested_model: str,
        routed_provider: str,
        routed_model: str,
        latency_ms: float,
        tokens_in: int,
        tokens_out: int,
        status_code: int,
        error_message: Optional[str] = None
    ) -> None:
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO request_logs (timestamp, key_id, requested_model, routed_provider, routed_model, latency_ms, tokens_in, tokens_out, status_code, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (now, key_id, requested_model, routed_provider, routed_model, latency_ms, tokens_in, tokens_out, status_code, error_message))
            conn.commit()

    def get_analytics(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total_requests, AVG(latency_ms) as avg_latency, SUM(tokens_in + tokens_out) as total_tokens FROM request_logs")
            overall = dict(cursor.fetchone() or {})

            cursor.execute("SELECT routed_provider, COUNT(*) as count FROM request_logs GROUP BY routed_provider ORDER BY count DESC LIMIT 10")
            providers = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT id, timestamp, requested_model, routed_provider, routed_model, latency_ms, status_code FROM request_logs ORDER BY id DESC LIMIT 15")
            recent_logs = [dict(r) for r in cursor.fetchall()]

            return {
                "total_requests": overall.get("total_requests") or 0,
                "avg_latency_ms": round(overall.get("avg_latency") or 0, 1),
                "total_tokens_saved": overall.get("total_tokens") or 0,
                "provider_distribution": providers,
                "recent_logs": recent_logs,
            }

    # --- Provider Credentials Store ---
    def set_provider_credential(self, provider_id: str, api_key: str, base_url: str = "") -> None:
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO provider_credentials (provider_id, api_key, base_url, is_active, updated_at)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(provider_id) DO UPDATE SET api_key=excluded.api_key, base_url=excluded.base_url, updated_at=excluded.updated_at
            """, (provider_id, api_key, base_url, now))
            conn.commit()

    def get_provider_credential(self, provider_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM provider_credentials WHERE provider_id = ? AND is_active = 1", (provider_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


# Global singleton instance
db = Database()
