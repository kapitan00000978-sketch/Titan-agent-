from titan_agent.core.reasoning.consensus_engine import (
    ConsensusEngine,
    VoteType,
)


def test_consensus_engine_approves_safe_proposal():
    proposal = "Introduce an AST-based function patcher to avoid offset bugs."
    context = "Python 3.10+ AST available in standard library."

    memo = ConsensusEngine.evaluate_heuristic(proposal, context)
    assert memo.verdict in ("APPROVED", "APPROVED_WITH_CONDITIONS")
    assert memo.consensus_score >= 0.70
    assert len(memo.ballots) == 3
    assert "FORMAL CONSENSUS MEMO" in memo.format_memo()


def test_consensus_engine_rejects_command_injection_hazard():
    proposal = "Execute user supplied strings directly with subprocess shell=True and eval()."
    memo = ConsensusEngine.evaluate_heuristic(proposal)

    assert memo.verdict == "REJECTED"
    sec_ballot = next(b for b in memo.ballots if b.role == "SecurityOfficer")
    assert sec_ballot.vote == VoteType.REJECT
    assert sec_ballot.score <= 0.3
    assert "Destructive or injection-prone" in sec_ballot.rationale


def test_consensus_engine_requires_conditions_for_credentials():
    proposal = "Store the user API token and database password in config cache."
    memo = ConsensusEngine.evaluate_heuristic(proposal)

    assert memo.verdict == "APPROVED_WITH_CONDITIONS"
    sec_ballot = next(b for b in memo.ballots if b.role == "SecurityOfficer")
    assert sec_ballot.vote == VoteType.APPROVE_WITH_CONDITIONS
    assert any("secret" in c.lower() or "isolation" in c.lower() for c in memo.action_items)


def test_consensus_engine_pragmatist_rejects_missing_docker():
    proposal = "Deploy service directly using docker run container."
    context = "Host environment check: docker is not installed."

    memo = ConsensusEngine.evaluate_heuristic(proposal, context)
    prag_ballot = next(b for b in memo.ballots if b.role == "Pragmatist")
    assert prag_ballot.vote == VoteType.REJECT
    assert "native tempdir fallback" in str(prag_ballot.required_conditions)
