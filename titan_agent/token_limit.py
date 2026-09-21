"""Token throughput guardrail for TITAN AGENT.

The agent must never exceed a hard token-per-second budget, no matter how many
providers, parallel tool turns or long streams are running. A token bucket
allows up to `TOKEN_RATE_LIMIT_PER_SEC` tokens per second (default 214,000)
and throttles any call that would burst over the cap.
"""
import asyncio
import time
from typing import Any

from .config import TOKEN_RATE_LIMIT_PER_SEC


def estimate_tokens(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    max_output: int = 4096,
) -> int:
    """Rough token estimate for a chat request: ~4 chars per token.

    Used to reserve budget BEFORE a call so the cap is enforced on the way in,
    not afterwards. Input (messages + serialized tools) plus the max_output
    allowance we are willing to reserve.
    """
    chars = 0
    for m in messages:
        content = m.get("content") or ""
        if isinstance(content, str):
            chars += len(content)
    if tools:
        chars += len(str(tools))
    return max(1, int(chars / 4)) + max(1, int(max_output))


class TokenRateLimiter:
    """Token-bucket rate limiter (async).

    The bucket holds up to `tokens_per_sec` tokens (one second of burst) and
    refills at `tokens_per_sec` tokens/second. `acquire(n)` withdraws `n`
    tokens; if the bucket is empty the caller waits exactly long enough for the
    tokens to refill, so the cumulative rate never exceeds the cap.

    With the default 214,000 tokens/s the guard is effectively invisible in
    production, but the accounting is real and testable with tiny rates.
    """

    def __init__(self, tokens_per_sec: int = TOKEN_RATE_LIMIT_PER_SEC):
        self.rate = int(tokens_per_sec)
        self.capacity = float(max(1, self.rate))
        self._tokens = self.capacity  # start with a full second of burst
        self._last = time.monotonic()
        self._lock = asyncio.Lock()
        # Accounting (visible via /api/token-usage)
        self.total_tokens_reserved = 0
        self.total_wait_seconds = 0.0
        self.calls = 0
        self.max_wait_seconds = 0.0

    async def acquire(self, tokens: int) -> float:
        """Reserve `tokens` against the per-second budget; wait if needed.

        Returns the throttling wait in seconds (0.0 when under the cap).
        """
        if tokens <= 0:
            return 0.0
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last = now

            if tokens <= self._tokens:
                self._tokens -= tokens
                wait = 0.0
            else:
                wait = (tokens - self._tokens) / self.rate
                self._tokens = 0.0
                # Reserve the refill time so concurrent awaiters queue fairly.
                self._last = now + wait

            self.total_tokens_reserved += tokens
            self.calls += 1
            self.total_wait_seconds += wait
            self.max_wait_seconds = max(self.max_wait_seconds, wait)

        if wait > 0:
            await asyncio.sleep(wait)
        return wait

    def stats(self) -> dict[str, Any]:
        return {
            "cap_per_second": self.rate,
            "total_tokens_reserved": self.total_tokens_reserved,
            "calls": self.calls,
            "total_wait_seconds": round(self.total_wait_seconds, 4),
            "max_wait_seconds": round(self.max_wait_seconds, 4),
        }