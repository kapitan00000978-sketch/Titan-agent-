"""Tests for Phase 27: Capability-Based Model Routing & Cognitive Budget."""
from titan_agent.core.routing.cost_tracker import CognitiveBudgetTracker
from titan_agent.core.routing.model_router import ModelRouter, ModelTier
from titan_agent.tools import ToolRegistry


def test_model_router_tier_classification():
    router = ModelRouter()

    # 1. Simple lookup / summary -> FAST_CHEAP
    fast_dec = router.route("Summarize the text in readme.md and list features")
    assert fast_dec.tier == ModelTier.FAST_CHEAP
    assert fast_dec.model_name in ("gpt-4o-mini", "gemini-1.5-flash", "claude-3-5-haiku")

    # 2. Coding & Implementation -> STANDARD_CODING
    code_dec = router.route("Implement a REST endpoint with unit tests for user authentication")
    assert code_dec.tier == ModelTier.STANDARD_CODING
    assert code_dec.model_name in ("claude-3-5-sonnet", "gpt-4o", "deepseek-coder")

    # 3. Deep Reasoning / Architecture / Debate -> DEEP_REASONING
    deep_dec = router.route("Analyze the distributed architecture trade-offs and solve this concurrency deadlock issue")
    assert deep_dec.tier == ModelTier.DEEP_REASONING
    assert deep_dec.model_name in ("deepseek-reasoner", "o3-mini", "o1")


def test_model_router_escalation():
    router = ModelRouter()

    # Normally fast cheap task
    base_dec = router.route("explain what is an api", prior_failures=0)
    assert base_dec.tier == ModelTier.FAST_CHEAP
    assert not base_dec.is_escalated

    # Promoted on 1 failure
    esc_dec1 = router.route("explain what is an api", prior_failures=1)
    assert esc_dec1.tier == ModelTier.STANDARD_CODING
    assert esc_dec1.is_escalated

    # Fully promoted to deep reasoning on 2+ failures
    esc_dec2 = router.route("explain what is an api", prior_failures=2)
    assert esc_dec2.tier == ModelTier.DEEP_REASONING
    assert esc_dec2.is_escalated


def test_cognitive_budget_tracker():
    tracker = CognitiveBudgetTracker(budget_limit_usd=1.0)

    # Record 100k input, 20k output tokens for gpt-4o-mini
    # gpt-4o-mini: $0.15 / 1M in, $0.60 / 1M out
    # in: 100,000 * 0.15 / 1,000,000 = $0.015
    # out: 20,000 * 0.60 / 1,000,000 = $0.012
    # expected = $0.027
    cost = tracker.record_usage("gpt-4o-mini", input_tokens=100_000, output_tokens=20_000)
    assert round(cost, 5) == 0.02700

    summary = tracker.get_summary()
    assert summary["total_input_tokens"] == 100_000
    assert summary["total_output_tokens"] == 20_000
    assert summary["total_tokens"] == 120_000
    assert round(summary["total_cost_usd"], 4) == 0.0270
    assert not summary["is_budget_exceeded"]

    # Exceed budget
    tracker.record_usage("o1", input_tokens=100_000, output_tokens=50_000)
    assert tracker.is_budget_exceeded()

    text = tracker.format_status_text()
    assert "COGNITIVE BUDGET & TOKEN USAGE REPORT" in text
    assert "BUDGET ALERT" in text


def test_tools_model_routing_integration(tmp_path):
    registry = ToolRegistry(workspace=tmp_path)

    # Test tool_model_route
    route_out = registry.tool_model_route("Refactor the database schema and write migration scripts")
    assert "### MODEL ROUTE DECISION" in route_out
    assert "STANDARD_CODING" in route_out

    # Test tool_model_budget_status
    status_out = registry.tool_model_budget_status()
    assert "COGNITIVE BUDGET & TOKEN USAGE REPORT" in status_out
