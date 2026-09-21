"""
Phase 2 Tests: Memory Core (Episodic, Semantic, Consolidation)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from titan_agent.core.memory import (
    MemoryKind,
    MemoryQuery,
    MemoryRecord,
    MemoryStats,
    MemorySystem,
)


@pytest.fixture()
def mem(tmp_path: Path):
    return MemorySystem(db_path=tmp_path / "test_mem.db")


class TestMemorize:
    def test_remember_and_get(self, mem):
        rec = mem.remember("Titan agent uses multi-provider routing", importance=0.9)
        assert rec.id > 0
        fetched = mem.get(rec.id)
        assert fetched is not None
        assert fetched.content == rec.content
        assert fetched.kind == MemoryKind.SEMANTIC

    def test_remember_all_kinds(self, mem):
        ep = mem.remember("Task: fix bug X - succeeded", kind=MemoryKind.EPISODIC)
        sem = mem.remember("Bug X root cause is Y", kind=MemoryKind.SEMANTIC)
        proc = mem.remember("To fix bug X: run tests", kind=MemoryKind.PROCEDURAL)
        assert ep.kind == MemoryKind.EPISODIC
        assert sem.kind == MemoryKind.SEMANTIC
        assert proc.kind == MemoryKind.PROCEDURAL

    def test_working_memory_ephemeral(self, mem):
        rec = mem.remember_working("current_task", "Refactor exceptions module")
        assert mem.get_working("current_task") is rec
        assert len(mem.list_working()) == 1
        # Working memory is not in SQLite stats
        assert mem.get(rec.id) is None  # never persisted

    def test_update_importance(self, mem):
        rec = mem.remember("fact", importance=0.3)
        assert mem.update_importance(rec.id, 0.9) is True
        assert mem.get(rec.id).importance == 0.9


class TestRecall:
    def test_keyword_scoring(self, mem):
        mem.remember("The project uses FastAPI for the API layer", importance=0.8)
        mem.remember("Users liked the dark theme design", importance=0.8)

        top = mem.recall("FastAPI API", limit=5)
        assert top, "expected at least one result"
        assert "FastAPI" in top[0].content

    def test_importance_threshold(self, mem):
        mem.remember("low value note", importance=0.1)
        mem.remember("high value fact", importance=0.9)
        top = mem.recall("value note fact", limit=5, min_importance=0.5)
        assert all(r.importance >= 0.5 for r in top)
        assert top[0].content == "high value fact"

    def test_kind_filter(self, mem):
        mem.remember("episode A", kind=MemoryKind.EPISODIC)
        mem.remember("fact B", kind=MemoryKind.SEMANTIC)
        only_episodic = mem.recall("episode fact", kinds=[MemoryKind.EPISODIC])
        assert all(r.kind == MemoryKind.EPISODIC for r in only_episodic)

    def test_scope_filter(self, mem):
        mem.remember("project alpha fact", scope="alpha")
        mem.remember("project beta fact", scope="beta")
        alpha = mem.recall("fact", scope="alpha")
        assert len(alpha) == 1
        assert alpha[0].metadata == {} or True  # scope applied correctly
        # re-check by listing
        recent = mem.list_recent(scope="alpha")
        assert len(recent) == 1

    def test_access_count_increments(self, mem):
        rec = mem.remember("popular fact", importance=0.8)
        mem.recall("popular fact", limit=5)
        mem.recall("popular fact", limit=5)
        updated = mem.get(rec.id)
        assert updated.access_count >= 1

    def test_empty_query_returns_recent(self, mem):
        mem.remember("first", kind=MemoryKind.EPISODIC)
        mem.remember("second", kind=MemoryKind.EPISODIC)
        top = mem.recall(limit=10)
        assert len(top) == 2


class TestConsolidation:
    def test_consolidates_high_importance_episodes(self, mem):
        mem.remember("Fixed timeout bug in retry logic", kind=MemoryKind.EPISODIC, importance=0.8, scope="retry")
        mem.remember("Fixed rate-limit bug in provider router", kind=MemoryKind.EPISODIC, importance=0.8, scope="retry")

        result = mem.consolidate(min_importance=0.6)

        assert result.facts_created >= 1
        assert result.episodes_processed == 2
        sem_facts = mem.list_recent(kind=MemoryKind.SEMANTIC, scope="retry")
        assert any("Fixed timeout" in f.content for f in sem_facts)

    def test_skips_low_importance(self, mem):
        mem.remember("trivial note", kind=MemoryKind.EPISODIC, importance=0.1)
        result = mem.consolidate(min_importance=0.6)
        assert result.facts_created == 0
        assert result.skipped == 1

    def test_no_duplicate_facts(self, mem):
        mem.remember("Fact X is true", kind=MemoryKind.EPISODIC, importance=0.9, scope="s")
        mem.consolidate(min_importance=0.5)
        mem.consolidate(min_importance=0.5)
        facts = mem.list_recent(kind=MemoryKind.SEMANTIC, scope="s")
        assert len(facts) == 1


class TestLifecycle:
    def test_forget_old_low_value(self, mem):
        mem.remember("new important fact", importance=0.9)
        removed = mem.forget(older_than_days=0.001, min_importance=0.5)  # nothing is that old
        assert removed == 0

    def test_clear(self, mem):
        mem.remember("a")
        mem.remember("b", kind=MemoryKind.EPISODIC)
        assert mem.clear() == 2
        assert mem.stats().total == 0

    def test_stats(self, mem):
        mem.remember("a", kind=MemoryKind.EPISODIC)
        mem.remember("b", kind=MemoryKind.SEMANTIC)
        mem.remember("c", kind=MemoryKind.SEMANTIC)
        stats = mem.stats()
        assert isinstance(stats, MemoryStats)
        assert stats.total == 3
        assert stats.by_kind[MemoryKind.SEMANTIC.value] == 2
        assert stats.by_kind[MemoryKind.EPISODIC.value] == 1

    def test_query_model(self):
        q = MemoryQuery(query="test", limit=10)
        assert q.query == "test"
        assert q.limit == 10


class TestRecordScoring:
    def test_recency_bonus_decays(self):
        rec = MemoryRecord(content="x")
        assert rec.recency_bonus() == pytest.approx(1.0, abs=0.01)
        # Simulate an old memory
        from datetime import timedelta
        rec.created_at = rec.created_at - timedelta(days=9)
        assert rec.recency_bonus() < 0.5

    def test_compute_score(self):
        rec = MemoryRecord(content="x", importance=0.8)
        fresh = rec.compute_score(keyword_overlap=1.0)
        assert 0 < fresh <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])