"""Unit tests for System 3 Metacognitive Overseer & Bayesian Hypothesis Engine."""
import pytest
from titan_agent.core.reasoning.metacognitive_overseer import (
    InterventionType,
    MetacognitiveOverseer,
)


def test_initial_hypotheses_and_bayesian_update():
    overseer = MetacognitiveOverseer("Fix the syntax error in the parser module")
    assert "H1_CODE_DEFECT" in overseer.hypotheses
    initial_p = overseer.hypotheses["H1_CODE_DEFECT"].probability
    assert initial_p == 0.6

    # Support with strong evidence
    new_p = overseer.update_bayesian_evidence("H1_CODE_DEFECT", "Syntax error found on line 42", supports=True, evidence_strength=0.8)
    assert new_p > initial_p

    # Refute with contrary evidence
    down_p = overseer.update_bayesian_evidence("H1_CODE_DEFECT", "Parser runs 100% fine in unit test", supports=False, evidence_strength=0.8)
    assert down_p < new_p


def test_entropy_and_repetition_calculation():
    overseer = MetacognitiveOverseer("general task")
    assert overseer.calculate_cognitive_entropy() == 0.0

    # Add 4 identical calls
    for i in range(4):
        overseer.evaluate_step(i, "trying again", "read_file", {"path": "a.txt"}, "Error: not found")

    assert overseer.calculate_repetition_score() == 0.75
    report = overseer.evaluate_step(5, "trying again", "read_file", {"path": "a.txt"}, "Error: not found")
    # Repetitive errors should trigger tool synthesis intervention
    assert report.intervention == InterventionType.TRIGGER_TOOL_SYNTHESIS
    assert "Synthesize a custom Python tool" in report.recommendation
