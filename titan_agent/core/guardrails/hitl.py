"""
Human-in-the-Loop - approval gates for sensitive operations.

Cline-style: every guarded action waits for explicit approval,
with timeout policy and audit of who approved what.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    """A single action waiting for human approval."""

    request_id: str = field(default_factory=lambda: str(uuid4())[:12])
    action: str = ""
    resource: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None
    decided_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action": self.action,
            "resource": self.resource,
            "details": self.details,
            "reason": self.reason,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decided_by": self.decided_by,
        }


class HumanInTheLoop:
    """Manages approval requests with async waiting and timeouts."""

    def __init__(
        self,
        default_timeout: float = 300.0,
        audit_path: Path | str | None = None,
    ):
        self.default_timeout = default_timeout
        self.audit_path = Path(audit_path) if audit_path else None
        self._requests: dict[str, ApprovalRequest] = {}
        self._waiters: dict[str, asyncio.Future] = {}

    # ---------- Request lifecycle ----------

    def request(
        self,
        action: str,
        resource: str = "*",
        details: dict[str, Any] | None = None,
        reason: str = "",
    ) -> ApprovalRequest:
        """Create a pending approval request."""
        req = ApprovalRequest(
            action=action,
            resource=resource,
            details=details or {},
            reason=reason,
        )
        self._requests[req.request_id] = req
        return req

    async def wait(
        self,
        req: ApprovalRequest,
        timeout: float | None = None,
    ) -> ApprovalRequest:
        """Wait for the request to be decided (or time out)."""
        if req.status != ApprovalStatus.PENDING:
            return req
        waiter: asyncio.Future = asyncio.get_running_loop().create_future()
        self._waiters[req.request_id] = waiter
        try:
            await asyncio.wait_for(waiter, timeout or self.default_timeout)
        except asyncio.TimeoutError:
            self.decide(req.request_id, ApprovalStatus.TIMED_OUT, "timeout")
        return req

    def approve(self, request_id: str, by: str = "human") -> ApprovalRequest | None:
        return self.decide(request_id, ApprovalStatus.APPROVED, by)

    def deny(self, request_id: str, by: str = "human") -> ApprovalRequest | None:
        return self.decide(request_id, ApprovalStatus.DENIED, by)

    def decide(
        self,
        request_id: str,
        status: ApprovalStatus | str,
        by: str = "system",
    ) -> ApprovalRequest | None:
        req = self._requests.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return req
        req.status = status if isinstance(status, ApprovalStatus) else ApprovalStatus(status)
        req.decided_at = datetime.now(timezone.utc)
        req.decided_by = by
        self._resolve_waiter(request_id)
        self._log(req)
        return req

    def cancel(self, request_id: str) -> ApprovalRequest | None:
        return self.decide(request_id, ApprovalStatus.CANCELLED, "system")

    def pending(self) -> list[ApprovalRequest]:
        return [
            r for r in self._requests.values()
            if r.status == ApprovalStatus.PENDING
        ]

    def get(self, request_id: str) -> ApprovalRequest | None:
        return self._requests.get(request_id)

    # ---------- Convenience ----------

    async def request_and_wait(
        self,
        action: str,
        resource: str = "*",
        details: dict[str, Any] | None = None,
        reason: str = "",
        timeout: float | None = None,
    ) -> ApprovalRequest:
        """Create a request and wait for a human decision."""
        req = self.request(action, resource, details, reason)
        return await self.wait(req, timeout)

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self._requests.values():
            key = r.status.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    # ---------- Internals ----------

    def _resolve_waiter(self, request_id: str) -> None:
        waiter = self._waiters.pop(request_id, None)
        if waiter and not waiter.done():
            waiter.set_result(True)

    def _log(self, req: ApprovalRequest) -> None:
        if not self.audit_path:
            return
        try:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(req.to_dict()) + "\n")
        except OSError:
            pass