"""
Phase 27 — Genesis Darajasi 7: Capability-Based Model Routing.

Selects the optimal model tier (FAST_CHEAP, STANDARD_CODING, DEEP_REASONING)
based on task complexity, coding needs, and dynamic failure escalation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar


class ModelTier(str, Enum):
    FAST_CHEAP = "fast_cheap"
    STANDARD_CODING = "standard_coding"
    DEEP_REASONING = "deep_reasoning"


@dataclass
class ModelCapabilityProfile:
    """Capability and pricing profile for a model."""

    name: str
    tier: ModelTier
    input_cost_per_m: float  # USD per 1M input tokens
    output_cost_per_m: float  # USD per 1M output tokens
    max_context: int = 128_000
    coding_score: float = 8.0
    reasoning_score: float = 8.0


@dataclass
class RouteDecision:
    """Outcome of model routing."""

    tier: ModelTier
    model_name: str
    rationale: str
    estimated_input_cost_per_1k: float
    estimated_output_cost_per_1k: float
    is_escalated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier.value,
            "model_name": self.model_name,
            "rationale": self.rationale,
            "estimated_input_cost_per_1k": self.estimated_input_cost_per_1k,
            "estimated_output_cost_per_1k": self.estimated_output_cost_per_1k,
            "is_escalated": self.is_escalated,
        }


class ModelRouter:
    """Routes tasks to model tiers based on intent, complexity, and escalation state."""

    DEFAULT_PROFILES: ClassVar[dict[str, ModelCapabilityProfile]] = {
        # FAST_CHEAP
        "gpt-4o-mini": ModelCapabilityProfile(
            name="gpt-4o-mini",
            tier=ModelTier.FAST_CHEAP,
            input_cost_per_m=0.15,
            output_cost_per_m=0.60,
            max_context=128_000,
            coding_score=7.5,
            reasoning_score=7.0,
        ),
        "gemini-1.5-flash": ModelCapabilityProfile(
            name="gemini-1.5-flash",
            tier=ModelTier.FAST_CHEAP,
            input_cost_per_m=0.075,
            output_cost_per_m=0.30,
            max_context=1_000_000,
            coding_score=7.2,
            reasoning_score=7.2,
        ),
        "claude-3-5-haiku": ModelCapabilityProfile(
            name="claude-3-5-haiku",
            tier=ModelTier.FAST_CHEAP,
            input_cost_per_m=0.80,
            output_cost_per_m=4.00,
            max_context=200_000,
            coding_score=8.0,
            reasoning_score=7.8,
        ),
        # STANDARD_CODING
        "claude-3-5-sonnet": ModelCapabilityProfile(
            name="claude-3-5-sonnet",
            tier=ModelTier.STANDARD_CODING,
            input_cost_per_m=3.00,
            output_cost_per_m=15.00,
            max_context=200_000,
            coding_score=9.5,
            reasoning_score=9.0,
        ),
        "gpt-4o": ModelCapabilityProfile(
            name="gpt-4o",
            tier=ModelTier.STANDARD_CODING,
            input_cost_per_m=2.50,
            output_cost_per_m=10.00,
            max_context=128_000,
            coding_score=9.0,
            reasoning_score=8.8,
        ),
        "deepseek-coder": ModelCapabilityProfile(
            name="deepseek-coder",
            tier=ModelTier.STANDARD_CODING,
            input_cost_per_m=0.14,
            output_cost_per_m=0.28,
            max_context=128_000,
            coding_score=9.1,
            reasoning_score=8.5,
        ),
        # DEEP_REASONING
        "o3-mini": ModelCapabilityProfile(
            name="o3-mini",
            tier=ModelTier.DEEP_REASONING,
            input_cost_per_m=1.10,
            output_cost_per_m=4.40,
            max_context=200_000,
            coding_score=9.4,
            reasoning_score=9.8,
        ),
        "deepseek-reasoner": ModelCapabilityProfile(
            name="deepseek-reasoner",
            tier=ModelTier.DEEP_REASONING,
            input_cost_per_m=0.55,
            output_cost_per_m=2.19,
            max_context=128_000,
            coding_score=9.3,
            reasoning_score=9.7,
        ),
        "o1": ModelCapabilityProfile(
            name="o1",
            tier=ModelTier.DEEP_REASONING,
            input_cost_per_m=15.00,
            output_cost_per_m=60.00,
            max_context=200_000,
            coding_score=9.6,
            reasoning_score=9.9,
        ),
    }

    TIER_DEFAULT_MODELS: ClassVar[dict[ModelTier, str]] = {
        ModelTier.FAST_CHEAP: "gpt-4o-mini",
        ModelTier.STANDARD_CODING: "claude-3-5-sonnet",
        ModelTier.DEEP_REASONING: "deepseek-reasoner",
    }

    DEEP_REASONING_KEYWORDS: ClassVar[set[str]] = {
        "architecture",
        "architectural",
        "tradeoff",
        "trade-off",
        "mathematical",
        "proof",
        "prove",
        "complex refactor",
        "debate",
        "reflexion",
        "deadlock",
        "race condition",
        "dag planning",
        "concurrency bug",
        "security audit",
        "cryptographic",
        "formal verification",
    }

    CODING_KEYWORDS: ClassVar[set[str]] = {
        "implement",
        "write function",
        "create class",
        "bug",
        "fix",
        "test",
        "unit test",
        "refactor",
        "api endpoint",
        "rest api",
        "database",
        "schema",
        "query",
        "frontend",
        "backend",
        "component",
    }

    FAST_KEYWORDS: ClassVar[set[str]] = {
        "read",
        "summarize",
        "explain",
        "what is",
        "status",
        "list",
        "check",
        "format",
        "help",
        "hello",
        "hi",
        "git status",
        "find file",
    }

    def __init__(self, custom_profiles: dict[str, ModelCapabilityProfile] | None = None):
        self.profiles = dict(self.DEFAULT_PROFILES)
        if custom_profiles:
            self.profiles.update(custom_profiles)

    def route(
        self,
        task: str,
        preferred_model: str = "",
        prior_failures: int = 0,
    ) -> RouteDecision:
        """
        Determines the optimal model tier and model name for a given task.
        Escalates tier if prior attempts failed.
        """
        text = str(task).lower().strip()
        tokens = set(re.findall(r"\w+", text))

        # Check for explicit model preference if supported
        if preferred_model and preferred_model in self.profiles:
            prof = self.profiles[preferred_model]
            return RouteDecision(
                tier=prof.tier,
                model_name=prof.name,
                rationale=f"User specified preferred model: {preferred_model}",
                estimated_input_cost_per_1k=prof.input_cost_per_m / 1000.0,
                estimated_output_cost_per_1k=prof.output_cost_per_m / 1000.0,
                is_escalated=False,
            )

        # Failure escalation: automatically promote if prior attempts failed
        if prior_failures >= 2:
            tier = ModelTier.DEEP_REASONING
            model_name = self.TIER_DEFAULT_MODELS[tier]
            prof = self.profiles[model_name]
            return RouteDecision(
                tier=tier,
                model_name=model_name,
                rationale=f"Escalated to {tier.value} due to {prior_failures} prior failures.",
                estimated_input_cost_per_1k=prof.input_cost_per_m / 1000.0,
                estimated_output_cost_per_1k=prof.output_cost_per_m / 1000.0,
                is_escalated=True,
            )

        # Check keyword matches
        deep_hits = sum(1 for kw in self.DEEP_REASONING_KEYWORDS if kw in text)
        coding_hits = sum(1 for kw in self.CODING_KEYWORDS if kw in text)
        fast_hits = sum(1 for kw in self.FAST_KEYWORDS if kw in text)

        # Complexity heuristics
        if deep_hits > 0 or len(text) > 2000:
            tier = ModelTier.DEEP_REASONING
            rationale = "Task requires deep architectural reasoning, formal logic, or complex analysis."
        elif fast_hits > 0 and coding_hits == 0:
            tier = ModelTier.FAST_CHEAP
            rationale = "Task is lightweight query, inspection, or informational lookup."
        elif coding_hits > 0 or "```" in text or len(tokens) > 60:
            tier = ModelTier.STANDARD_CODING
            rationale = "Task involves software implementation, debugging, or code generation."
        elif fast_hits > 0 or len(tokens) < 25:
            tier = ModelTier.FAST_CHEAP
            rationale = "Task is lightweight query, inspection, or informational lookup."
        else:
            tier = ModelTier.STANDARD_CODING
            rationale = "Standard complexity general task."

        # Escalation bump if 1 failure occurred
        is_escalated = False
        if prior_failures == 1 and tier == ModelTier.FAST_CHEAP:
            tier = ModelTier.STANDARD_CODING
            rationale += " (Promoted from fast_cheap due to prior retry)"
            is_escalated = True

        model_name = self.TIER_DEFAULT_MODELS[tier]
        prof = self.profiles[model_name]

        return RouteDecision(
            tier=tier,
            model_name=model_name,
            rationale=rationale,
            estimated_input_cost_per_1k=prof.input_cost_per_m / 1000.0,
            estimated_output_cost_per_1k=prof.output_cost_per_m / 1000.0,
            is_escalated=is_escalated,
        )
