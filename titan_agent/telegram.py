"""Telegram account manager — Titan Agent capability.

SAFETY MODEL (user-consented on purpose):
  * Everything is gated behind TITAN_TELEGRAM_ENABLED=true in .env — the agent
    cannot touch Telegram unless the user explicitly turns the capability on.
  * Login requires the USER's own phone + the one-time code Telegram sends them.
    The agent can never log in on its own: no phone, no code => no account.
  * Sending messages is additionally gated by TITAN_TELEGRAM_SEND_ALLOWLIST
    (comma-separated targets). With an empty allowlist the agent can read but
    never send — spam/broadcast tooling is intentionally NOT built.
  * Sessions live under workspace/telegram_sessions/ (git-ignored). Phone
    numbers/usernames are masked in every output; api_hash is never printed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import (
    TITAN_TELEGRAM_API_HASH,
    TITAN_TELEGRAM_API_ID,
    TITAN_TELEGRAM_ENABLED,
    TITAN_TELEGRAM_SEND_ALLOWLIST,
    WORKSPACE_DIR,
)

SESSION_DIR = WORKSPACE_DIR / "telegram_sessions"


def _mask_phone(phone: str) -> str:
    """+998901234567 -> +998 ** *** ** 67 (middle digits always hidden)."""
    digits = [c for c in str(phone) if c.isdigit()]
    if len(digits) < 6:
        return "***"
    keep_head, keep_tail = 3, 2
    head = "".join(digits[:keep_head])
    tail = "".join(digits[-keep_tail:])
    return f"+{head} ** *** ** {tail}"


def _mask_username(username: str) -> str:
    if not username:
        return "(no username)"
    name = str(username)
    if len(name) <= 4:
        return name[0] + "*" * (len(name) - 1) + ("*" if len(name) > 1 else "")
    return name[:2] + "*" * (len(name) - 4) + name[-2:]


class TelegramError(RuntimeError):
    """Raised for consent/file/connection problems with a user-safe message."""


class TelegramManager:
    """Async wrapper around Telethon with the consent + allowlist safety gates.

    Network methods are synchronous helpers that are safe to call from the
    agent/server (they run fast and are not hot paths); an async shell is
    provided for server endpoints if ever needed.
    """

    def __init__(self, session_dir: Path | None = None):
        self.session_dir = Path(session_dir or SESSION_DIR)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._pending: dict[str, Any] = {}  # label -> TelethonClient during login

    # ------------------------------------------------------------------ info
    def enabled(self) -> bool:
        return bool(TITAN_TELEGRAM_ENABLED)

    def has_credentials(self) -> bool:
        return bool(TITAN_TELEGRAM_API_ID and TITAN_TELEGRAM_API_HASH)

    def send_allowlist(self) -> list[str]:
        raw = (TITAN_TELEGRAM_SEND_ALLOWLIST or "").strip()
        if not raw:
            return []
        return [x.strip().lstrip("@").lower() for x in raw.split(",") if x.strip()]

    def _require_enabled(self) -> None:
        if not self.enabled():
            raise TelegramError(
                "Telegram control is disabled. To enable it, set "
                "TITAN_TELEGRAM_ENABLED=true plus TITAN_TELEGRAM_API_ID and "
                "TITAN_TELEGRAM_API_HASH in .env (get them at https://my.telegram.org)."
            )
        if not self.has_credentials():
            raise TelegramError(
                "TITAN_TELEGRAM_API_ID / TITAN_TELEGRAM_API_HASH are not set in .env. "
                "Get them at https://my.telegram.org -> API development tools."
            )

    def _telethon(self):
        try:
            from telethon import TelegramClient
            return TelegramClient
        except ImportError:
            raise TelegramError(
                "Telethon is not installed. Run:  python -m pip install telethon"
            )

    def _session_file(self, label: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
        return self.session_dir / f"{safe}.session"

    def _meta_file(self, label: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
        return self.session_dir / f"{safe}.meta.json"

    def _read_meta(self, label: str) -> dict[str, Any]:
        try:
            return json.loads(self._meta_file(label).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_meta(self, label: str, data: dict[str, Any]) -> None:
        self._meta_file(label).write_text(json.dumps(data), encoding="utf-8")

    def _accounts(self) -> list[dict[str, Any]]:
        out = []
        if not self.session_dir.exists():
            return out
        for s in sorted(self.session_dir.glob("*.session")):
            label = s.name[: -len(".session")]
            meta = self._read_meta(label)
            out.append(
                {
                    "label": label,
                    "phone": _mask_phone(meta.get("phone", "")),
                    "username": _mask_username(meta.get("username", "")),
                    "added": meta.get("added", ""),
                }
            )
        return out

    def status(self) -> dict[str, Any]:
        creds = self.has_credentials()
        allow = self.send_allowlist()
        return {
            "enabled": self.enabled(),
            "credentials_set": creds,
            "api_id_set": bool(TITAN_TELEGRAM_API_ID),
            "api_hash_set": bool(TITAN_TELEGRAM_API_HASH),
            "sessions": len(self._accounts()),
            "send_allowlist_entries": len(allow),
            "send_allowlist": allow if allow else [],
            "session_dir": str(self.session_dir),
        }

    def list_accounts(self) -> list[dict[str, Any]]:
        self._require_enabled()
        return self._accounts()

    # ------------------------------------------------------------ login flow
    def login_start(self, label: str, phone: str) -> dict[str, Any]:
        """Ask the API to send a login code to `phone`. Consent: the phone
        belongs to the user; completing the flow below is their explicit act."""
        self._require_enabled()
        if not label.strip() or not phone.strip():
            raise TelegramError("login_start requires both 'label' and 'phone'.")
        client_cls = self._telethon()
        client = client_cls(
            str(self._session_file(label)),
            int(TITAN_TELEGRAM_API_ID),
            TITAN_TELEGRAM_API_HASH,
        )
        try:
            client.connect()
        except OSError as e:  # pragma: no cover - network path
            raise TelegramError(f"Could not reach Telegram servers: {type(e).__name__}")
        self._pending[label.strip()] = client
        return {
            "status": "code_requested",
            "label": label.strip(),
            "note": (
                "A login code was sent to that phone in Telegram. Ask the user for "
                "the code and pass it to telegram_login_confirm — never guess it."
            ),
        }

    def login_confirm(self, label: str, code: str) -> dict[str, Any]:
        """Complete login with the user-provided one-time code."""
        self._require_enabled()
        client = self._pending.pop(label, None)
        if client is None:
            raise TelegramError(
                f"No pending login for '{label}'. Run telegram_login_start first."
            )
        try:
            client.sign_in(code=str(code).strip())
        except OSError as e:  # pragma: no cover - network path
            raise TelegramError(f"Login failed (wrong/expired code?): {type(e).__name__}")
        me = client.get_me()
        meta = {
            "phone": (me.phone or "") if me else "",
            "username": (me.username or "") if me else "",
            "added": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self._write_meta(label, meta)
        client.disconnect()
        return {
            "status": "logged_in",
            "label": label,
            "phone": _mask_phone(meta["phone"]),
            "username": _mask_username(meta["username"]),
        }

    # ---------------------------------------------------------------- actions
    def send_message(self, label: str, target: str, text: str) -> dict[str, Any]:
        """Send a message ONLY to an allowlisted target (user-consented safety)."""
        self._require_enabled()
        allow = self.send_allowlist()
        if not allow:
            raise TelegramError(
                "Sending is disabled: TITAN_TELEGRAM_SEND_ALLOWLIST is empty in .env. "
                "Add the target to the allowlist to allow sending to it."
            )
        if not text.strip():
            raise TelegramError("send_message requires 'text'.")
        key = str(target).strip().lstrip("@").lower()
        if not key:
            raise TelegramError("send_message requires 'target'.")
        if key not in allow:
            raise TelegramError(
                f"Sending to '{target}' is not allowed. Allowed targets from "
                f".env TITAN_TELEGRAM_SEND_ALLOWLIST: {', '.join(allow) or '(none)'}"
            )
        client = self._open(label)
        try:
            client.send_message(target, text)
            return {"status": "sent", "label": label, "target": target, "chars": len(text)}
        finally:
            client.disconnect()

    def recent_messages(self, label: str, limit: int = 10) -> list[dict[str, Any]]:
        """Read-only: last messages from the account's own dialogs (masked senders)."""
        self._require_enabled()
        client = self._open(label)
        try:
            out = []
            for i, msg in enumerate(client.get_messages("me", limit=min(limit, 25))):
                sender = getattr(msg.sender, "username", None) or getattr(
                    msg.sender, "first_name", "?"
                )
                out.append(
                    {
                        "n": i + 1,
                        "from": _mask_username(str(sender)) if sender else "(saved message)",
                        "text": (msg.text or "")[:200],
                        "date": str(msg.date)[:19] if msg.date else "",
                    }
                )
            return out
        finally:
            client.disconnect()

    def whoami(self, label: str) -> dict[str, Any]:
        """Own profile for this session (masked)."""
        self._require_enabled()
        client = self._open(label)
        try:
            me = client.get_me()
            return {
                "label": label,
                "username": _mask_username((me.username or "") if me else ""),
                "phone": _mask_phone((me.phone or "") if me else ""),
                "first_name": ((me.first_name or "") if me else "") or "(private)",
            }
        finally:
            client.disconnect()

    def logout(self, label: str, delete: bool = False) -> dict[str, Any]:
        self._require_enabled()
        sess = self._session_file(label)
        if not sess.exists():
            raise TelegramError(f"No session named '{label}'.")
        if delete:
            try:
                client = self._open(label)
                try:
                    client.log_out()
                finally:
                    client.disconnect()
                self._session_file(label).unlink(missing_ok=True)
                self._meta_file(label).unlink(missing_ok=True)
            except OSError:
                self._session_file(label).unlink(missing_ok=True)
            return {"status": "deleted", "label": label}
        return {"status": "session_removed_locally", "label": label}

    # ---------------------------------------------------------------- helpers
    def _open(self, label: str):
        self._telethon()
        from telethon import TelegramClient
        client = TelegramClient(
            str(self._session_file(label)),
            int(TITAN_TELEGRAM_API_ID),
            TITAN_TELEGRAM_API_HASH,
        )
        try:
            client.connect()
            if not client.is_user_authorized():
                raise TelegramError(
                    f"Session '{label}' is not authorized. Run the login flow: "
                    "telegram_login_start + telegram_login_confirm with the user's code."
                )
            return client
        except TelegramError:
            client.disconnect()
            raise
        except OSError as e:  # pragma: no cover - network path
            client.disconnect()
            raise TelegramError(f"Could not open session '{label}': {type(e).__name__}")