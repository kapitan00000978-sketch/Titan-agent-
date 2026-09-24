"""
Phase 41 — System 3: Metacognitive Overseer & Bayesian Hypothesis Engine.

Operates as the self-reflective "Observer Mind" above System 1 (fast intuition)
and System 2 (deliberative planning). It monitors cognitive entropy, detects
hallucination drift, tracks Bayesian candidate hypotheses, and prescribes
autonomous strategy pivots (e.g. pivoting to MCTS, Multi-Agent Debate,
or Dynamic Tool Synthesis) before execution deadlocks occur.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InterventionType(str, Enum):
    CONTINUE = "continue"
    PIVOT_MCTS = "pivot_mcts"
    PIVOT_DEBATE = "pivot_debate"
    TRIGGER_TOOL_SYNTHESIS = "trigger_tool_synthesis"
    FORCE_HYPOTHESIS_PIVOT = "force_hypothesis_pivot"
    EARLY_HALT = "early_halt"


@dataclass
class Hypothesis:
    """A candidate explanation or approach for solving the task."""

    id: str
    statement: str
    probability: float = 0.5
    supporting_evidence: list[str] = field(default_factory=list)
    refuting_evidence: list[str] = field(default_factory=list)
    status: str = "active"  # "active", "confirmed", "refuted"


@dataclass
class MetacognitiveReport:
    """Snapshot assessment of the agent's current cognitive state."""

    step: int
    cognitive_entropy: float
    hallucination_drift: float
    repetition_score: float
    active_hypotheses: list[Hypothesis]
    intervention: InterventionType
    recommendation: str


class MetacognitiveOverseer:
    """Monitors, assesses, and directs the agent's reasoning loop."""

    def __init__(self, task: str):
        self.task = task
        self.task_keywords = set(re.findall(r"\w{3,}", task.lower()))
        self.recent_calls: list[tuple[str, str]] = []  # (tool_name, serialized_args)
        self.hypotheses: dict[str, Hypothesis] = {}
        self.step_history: list[dict[str, Any]] = []
        self._init_hypotheses_from_task(task)

    def _init_hypotheses_from_task(self, task: str) -> None:
        """Seeds initial working hypotheses based on task structure."""
        t_low = task.lower()
        if any(w in t_low for w in ["bug", "error", "fail", "broken", "fix", "tuzat"]):
            self.hypotheses["H1_CODE_DEFECT"] = Hypothesis(
                id="H1_CODE_DEFECT",
                statement="The issue is caused by a syntax, logic, or type defect in existing code.",
                probability=0.6,
            )
            self.hypotheses["H2_ENV_DEPENDENCY"] = Hypothesis(
                id="H2_ENV_DEPENDENCY",
                statement="The issue is caused by a missing dependency, path error, or environment mismatch.",
                probability=0.4,
            )
        else:
            self.hypotheses["H1_STANDARD_IMPLEMENTATION"] = Hypothesis(
                id="H1_STANDARD_IMPLEMENTATION",
                statement="The task can be accomplished using standard existing workspace tools and functions.",
                probability=0.7,
            )
            self.hypotheses["H2_CUSTOM_TOOL_REQUIRED"] = Hypothesis(
                id="H2_CUSTOM_TOOL_REQUIRED",
                statement="The task requires domain-specific custom tool synthesis or external protocol adapters.",
                probability=0.3,
            )

    def add_hypothesis(self, hid: str, statement: str, initial_prob: float = 0.5) -> Hypothesis:
        """Adds a new explicit hypothesis to the tracker."""
        hyp = Hypothesis(id=hid, statement=statement, probability=initial_prob)
        self.hypotheses[hid] = hyp
        return hyp

    def calculate_cognitive_entropy(self) -> float:
        """Calculates Shannon entropy across recent tool calls to detect repetitive loops."""
        if not self.recent_calls:
            return 0.0
        window = self.recent_calls[-8:]
        counts: dict[str, int] = {}
        for name, args in window:
            key = f"{name}:{args[:60]}"
            counts[key] = counts.get(key, 0) + 1
        total = len(window)
        entropy = 0.0
        for count in counts.values():
            p = count / total
            entropy -= p * math.log2(p)
        return round(entropy, 3)

    def calculate_repetition_score(self) -> float:
        """Calculates exact repetition ratio in the recent sliding window."""
        if len(self.recent_calls) < 2:
            return 0.0
        window = self.recent_calls[-6:]
        unique_keys = {f"{name}:{args}" for name, args in window}
        # If 6 calls made but only 1 unique -> 1.0 repetition
        repetition = 1.0 - (len(unique_keys) / len(window))
        return round(repetition, 3)

    def calculate_drift(self, thoughts: str, tool_result: str) -> float:
        """Measures drift away from the original task intent."""
        if not self.task_keywords:
            return 0.0
        combined = f"{thoughts} {tool_result}".lower()
        combined_words = set(re.findall(r"\w{3,}", combined))
        intersection = self.task_keywords.intersection(combined_words)
        overlap = len(intersection) / len(self.task_keywords)
        # Drift is inverse of overlap
        drift = max(0.0, 1.0 - overlap)
        return round(drift, 3)

    def update_bayesian_evidence(
        self,
        hypothesis_id: str,
        evidence: str,
        supports: bool,
        evidence_strength: float = 0.7,
    ) -> float:
        """Updates hypothesis probability using Bayes rule given new evidence."""
        hyp = self.hypotheses.get(hypothesis_id)
        if not hyp or hyp.status != "active":
            return 0.0

        p_h = hyp.probability
        # Likelihood P(E|H)
        p_e_given_h = evidence_strength if supports else (1.0 - evidence_strength)
        # Likelihood P(E|not H)
        p_e_given_not_h = (1.0 - evidence_strength) if supports else evidence_strength

        # Marginal P(E) = P(E|H)*P(H) + P(E|not H)*P(not H)
        p_e = (p_e_given_h * p_h) + (p_e_given_not_h * (1.0 - p_h))
        if p_e > 0:
            posterior = (p_e_given_h * p_h) / p_e
        else:
            posterior = p_h

        hyp.probability = round(min(0.99, max(0.01, posterior)), 3)
        if supports:
            hyp.supporting_evidence.append(evidence)
        else:
            hyp.refuting_evidence.append(evidence)

        if hyp.probability >= 0.85:
            hyp.status = "confirmed"
        elif hyp.probability <= 0.15:
            hyp.status = "refuted"

        return hyp.probability

    def evaluate_step(
        self,
        step_idx: int,
        thoughts: str,
        tool_name: str,
        tool_args: dict[str, Any],
        tool_result: str,
    ) -> MetacognitiveReport:
        """Assesses one completed step and prescribes metacognitive interventions."""
        try:
            serialized_args = json.dumps(tool_args, sort_keys=True, default=str)
        except Exception:
            serialized_args = repr(tool_args)

        self.recent_calls.append((tool_name, serialized_args))
        if len(self.recent_calls) > 20:
            del self.recent_calls[0]

        entropy = self.calculate_cognitive_entropy()
        repetition = self.calculate_repetition_score()
        drift = self.calculate_drift(thoughts, tool_result)

        # Update hypotheses based on tool outcomes
        is_error = "Error" in tool_result or "failed" in tool_result.lower()
        if "H1_CODE_DEFECT" in self.hypotheses:
            if is_error and ("syntax" in tool_result.lower() or "type" in tool_result.lower()):
                self.update_bayesian_evidence("H1_CODE_DEFECT", f"Error at step {step_idx}: {tool_result[:100]}", True, 0.75)
            elif is_error and ("not found" in tool_result.lower() or "module" in tool_result.lower()):
                self.update_bayesian_evidence("H2_ENV_DEPENDENCY", f"Missing dependency at step {step_idx}", True, 0.8)

        # Determine intervention
        intervention = InterventionType.CONTINUE
        recommendation = "Cognitive state healthy. Continue execution."

        # 1. High repetition or zero entropy with errors -> Stagnation loop
        if repetition >= 0.6 and is_error:
            intervention = InterventionType.TRIGGER_TOOL_SYNTHESIS
            recommendation = (
                f"Repeated tool failure detected (repetition={repetition}). Existing tools "
                f"('{tool_name}') are stuck in a dead-end. Synthesize a custom Python tool "
                "or pivot to dynamic tool creation to resolve this blocker."
            )
        elif repetition >= 0.6:
            intervention = InterventionType.PIVOT_MCTS
            recommendation = (
                f"Agent oscillating across identical tool calls ({tool_name}). "
                "Engage Monte Carlo Tree Search (MCTS) to branch out alternative solution paths."
            )
        elif drift > 0.85 and step_idx > 3:
            intervention = InterventionType.FORCE_HYPOTHESIS_PIVOT
            recommendation = (
                f"Critical semantic drift detected ({drift:.2f}). Re-anchor to the original "
                f"task: '{self.task[:100]}'. Drop current dead-end sub-problem."
            )
        elif step_idx > 10 and all(h.status != "confirmed" for h in self.hypotheses.values()):
            intervention = InterventionType.PIVOT_DEBATE
            recommendation = (
                "No hypothesis confirmed after 10 steps. Initiate multi-agent debate (Advocate vs Skeptic) "
                "to evaluate conflicting architectural theories."
            )

        report = MetacognitiveReport(
            step=step_idx,
            cognitive_entropy=entropy,
            hallucination_drift=drift,
            repetition_score=repetition,
            active_hypotheses=list(self.hypotheses.values()),
            intervention=intervention,
            recommendation=recommendation,
        )

        self.step_history.append({
            "step": step_idx,
            "entropy": entropy,
            "repetition": repetition,
            "drift": drift,
            "intervention": intervention.value,
        })
        return report

    def summary(self) -> dict[str, Any]:
        """Provides an executive summary of the metacognitive overseer."""
        return {
            "total_steps_monitored": len(self.step_history),
            "current_entropy": self.calculate_cognitive_entropy(),
            "hypotheses": {
                hid: {
                    "statement": h.statement,
                    "probability": h.probability,
                    "status": h.status,
                    "supports_count": len(h.supporting_evidence),
                    "refutes_count": len(h.refuting_evidence),
                }
                for hid, h in self.hypotheses.items()
            },
            "recent_interventions": [
                s for s in self.step_history if s["intervention"] != InterventionType.CONTINUE.value
            ],
        }
