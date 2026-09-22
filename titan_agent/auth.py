"""
Phase 12 — Server Authentication.

Every HTTP route except the public liveness check (`/health`) and the web-UI
shell (`/`) requires a Bearer token. The token is resolved, in priority order:

1. ``TITAN_API_KEY`` env var (explicit operator choice);
2. the persisted random key in ``workspace/.server_key`` (survives restarts);
3. a freshly generated key — persisted to ``workspace/.server_key`` and printed
   ONCE to the console so the operator can copy it.

``workspace/`` is already gitignored, so the persisted key is never committed.
"""
from __future__ import annotations

import logging
import secrets

from fastapi import Header, HTTPException, status

from .config import WORKSPACE_DIR

log = logging.getLogger(__name__)

SERVER_KEY_FILE = WORKSPACE_DIR / ".server_key"
_BEARER_PREFIX = "Bearer "
_printed_once = False


def _persisted_key() -> str | None:
    try:
        if SERVER_KEY_FILE.exists():
            stored = SERVER_KEY_FILE.read_text(encoding="utf-8").strip()
            return stored or None
    except OSError as exc:
        log.warning("Could not read persisted server key: %s", exc)
    return None


def _persist_key(key: str) -> None:
    try:
        SERVER_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        SERVER_KEY_FILE.write_text(key, encoding="utf-8")
    except OSError as exc:  # best-effort; fall back to env-only
        log.warning("Could not persist server key: %s", exc)


def get_server_api_key() -> str:
    """Resolve the server API key (env > persisted file > generated+persisted).

    Generation prints the key exactly once per process so operators can copy it.
    """
    import os

    global _printed_once

    env_key = os.getenv("TITAN_API_KEY", "").strip()
    if env_key:
        return env_key

    stored = _persisted_key()
    if stored:
        return stored

    generated = "sk-titan-" + secrets.token_urlsafe(32)
    _persist_key(generated)
    if not _printed_once:
        _printed_once = True
        banner = (
            "\n" + "=" * 70 + "\n"
            "TITAN AGENT — generated server API key (auth is ON for all /api routes).\n"
            "Saved to: " + str(SERVER_KEY_FILE) + "\n"
            "Set TITAN_API_KEY in .env to control it explicitly.\n"
            "KEY: " + generated + "\n"
            + "=" * 70
        )
        print(banner, flush=True)
        log.info("Generated and persisted a new server API key.")
    return generated


async def require_api_key(authorization: str = Header(default="")) -> str:
    """FastAPI dependency: reject any request without a valid Bearer token.

    Returns the resolved key on success; raises 401 otherwise.
    """
    if not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token. Provide 'Authorization: Bearer <TITAN_API_KEY>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[len(_BEARER_PREFIX):].strip()
    expected = get_server_api_key()
    if not token or token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


__all__ = ["SERVER_KEY_FILE", "get_server_api_key", "require_api_key"]
