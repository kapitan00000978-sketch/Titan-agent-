"""
Memory System Types - Episodic, Semantic, Procedural, Working memory records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class MemoryKind(str, Enum):
    """Categories of memory records."""

    EPISODIC = "episodic"        # What happened: sessions, tasks, outcomes
    SEMANTIC = "semantic"        # Facts and knowledge learned over time
    PROCEDURAL = "procedural"    # How-to skills and reusable procedures
    WORKING = "working"          # Current task context (not persisted)


class MemoryRecord(BaseModel):
    """A single memory record with retrieval scoring support."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int = 0
    uid: str = Field(default_factory=lambda: str(uuid4())[:12])
    kind: MemoryKind = MemoryKind.SEMANTIC
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    access_count: int = 0
    scope: str = "global"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Computed at retrieval time (not stored)
    score: float = 0.0

    def touch(self) -> None:
        """Mark as accessed now."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)

    def age_days(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        return max(0.0, (now - self.created_at).total_seconds() / 86400.0)

    def recency_bonus(self, now: datetime | None = None) -> float:
        """Decay factor: 1.0 for fresh, approaching 0 for old."""
        return 1.0 / (1.0 + self.age_days(now))

    def compute_score(
        self,
        keyword_overlap: float = 0.0,
        now: datetime | None = None,
    ) -> float:
        """
        Retrieval score = keyword relevance + recency + importance + access bias.

        - keyword_overlap: 0..1 fraction of query tokens matched
        - recency: 1/(1+days) so fresh memories rank higher
        - importance: user/agent assigned 0..1
        - access bias: frequently recalled memories are slightly preferred
        """
        recency = self.recency_bonus(now)
        access_bias = min(1.0, self.access_count / 10.0) * 0.05
        self.score = (
            keyword_overlap * 0.6
            + recency * 0.2
            + self.importance * 0.15
            + access_bias
        )
        return self.score


class MemoryQuery(BaseModel):
    """Query parameters for memory retrieval."""

    query: str = ""
    kinds: list[MemoryKind] | None = None
    limit: int = Field(default=5, ge=1, le=50)
    scope: str | None = None
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class MemoryStats(BaseModel):
    """Snapshot of memory system state."""

    total: int = 0
    by_kind: dict[str, int] = Field(default_factory=dict)
    oldest: datetime | None = None
    newest: datetime | None = None
    total_consolidations: int = 0


class ConsolidationResult(BaseModel):
    """Result of an episodic -> semantic consolidation pass."""

    episodes_processed: int = 0
    facts_created: int = 0
    skipped: int = 0
    details: list[str] = Field(default_factory=list)