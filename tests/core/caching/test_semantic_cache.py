from pathlib import Path
from titan_agent.core.caching.semantic_cache import SemanticCache


def test_semantic_cache_exact_and_fuzzy_hit(tmp_path):
    db_file = tmp_path / "test_cache.db"
    cache = SemanticCache(db_path=db_file, default_threshold=0.80)

    query = "How do I configure PostgreSQL connection pooling with SQLAlchemy?"
    answer = "Use QueuePool with pool_size=10 and max_overflow=20 in create_engine()."

    # Store in cache
    cache.set(query, answer, model="gpt-4o", estimated_tokens=150)

    # 1. Exact match lookup (100% similarity, 0ms)
    res, sim = cache.get(query)
    assert res == answer
    assert sim == 1.0

    # 2. Semantic fuzzy match (high word overlap)
    fuzzy_query = "How can I configure PostgreSQL connection pooling using SQLAlchemy?"
    fuzzy_res, fuzzy_sim = cache.get(fuzzy_query, threshold=0.70)
    assert fuzzy_res == answer
    assert fuzzy_sim >= 0.70

    # 3. Unrelated query (cache miss)
    unrelated_res, un_sim = cache.get("Write a CSS animation for a spinning loader.")
    assert unrelated_res is None
    assert un_sim < 0.40


def test_semantic_cache_metrics_and_savings(tmp_path):
    cache = SemanticCache(db_path=tmp_path / "cache_metrics.db")
    cache.set("What is 2+2?", "4", estimated_tokens=50)

    # 2 hits
    cache.get("What is 2+2?")
    cache.get("What is 2+2?")
    # 1 miss
    cache.get("What is the capital of Uzbekistan?")

    stats = cache.get_stats()
    assert stats.total_entries == 1
    assert stats.total_hits == 2
    assert stats.total_misses == 1
    assert stats.estimated_tokens_saved == 100
    assert "SEMANTIC CACHE STATS" in stats.summary()
