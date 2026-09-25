"""
Phase 63 — Multi-Agent Consensus & Deliberation Engine (Konsensus Qarorlar Mexanizmi).

Runs formal multi-perspective committee deliberation on critical architectural,
security, or code refactoring proposals, preventing reckless decisions through
weighted voting (Architect, Security Officer, Pragmatist) and signed consensus memos.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine


class VoteType(str, Enum):
    APPROVE = "APPROVE"
    APPROVE_WITH_CONDITIONS = "APPROVE_WITH_CONDITIONS"
    REJECT = "REJECT"


@dataclass
class MemberBallot:
    """Individual ballot from one committee member."""

    role: str
    vote: VoteType
    score: float  # 0.0 to 1.0
    rationale: str
    required_conditions: list[str] = field(default_factory=list)


@dataclass
class ConsensusMemo:
    """Formal consensus decision memo."""

    proposal: str
    verdict: str  # "APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED"
    consensus_score: float
    ballots: list[MemberBallot]
    action_items: list[str] = field(default_factory=list)

    def format_memo(self) -> str:
        icon = "✅" if self.verdict == "APPROVED" else ("⚠️" if self.verdict == "APPROVED_WITH_CONDITIONS" else "🚫")
        lines = [
            f"### FORMAL CONSENSUS MEMO: {icon} {self.verdict} (Score: {self.consensus_score * 100:.1f}%)",
            f"**Proposal**: {self.proposal}",
            "",
            "#### Committee Ballots:",
        ]
        for b in self.ballots:
            v_str = b.vote.value
            lines.append(f"- **{b.role}** [{v_str} - {b.score * 100:.0f}%]: {b.rationale}")
            for c in b.required_conditions:
                lines.append(f"  *Condition:* {c}")

        if self.action_items:
            lines.append("\n#### Consensus Directives:")
            for item in self.action_items:
                lines.append(f"1. {item}")

        return "\n".join(lines)


class ConsensusEngine:
    """Orchestrates committee evaluations and renders mathematical consensus."""

    ROLES = ("Architect", "SecurityOfficer", "Pragmatist")
    WEIGHTS = {"Architect": 0.35, "SecurityOfficer": 0.40, "Pragmatist": 0.25}

    @staticmethod
    def evaluate_heuristic(proposal: str, context: str = "") -> ConsensusMemo:
        """Deterministic heuristic evaluation when full LLM committee is not passed."""
        p_low = proposal.lower()
        c_low = context.lower()

        ballots: list[MemberBallot] = []

        # 1. Security Officer evaluation
        sec_concerns = []
        sec_score = 0.9
        sec_vote = VoteType.APPROVE
        if any(w in p_low for w in ["shell=true", "eval(", "exec(", "rm -rf", "delete_file", "format"]):
            sec_score = 0.2
            sec_vote = VoteType.REJECT
            sec_concerns.append("Destructive or injection-prone command pattern detected.")
        elif any(w in p_low for w in ["password", "token", "secret", "private_key", "credential"]):
            sec_score = 0.5
            sec_vote = VoteType.APPROVE_WITH_CONDITIONS
            sec_concerns.append("Ensure secret redaction and environment variable isolation.")

        ballots.append(
            MemberBallot(
                role="SecurityOfficer",
                vote=sec_vote,
                score=sec_score,
                rationale="Reviewed for attack surface, code execution risks, and secret exposure."
                if not sec_concerns else "; ".join(sec_concerns),
                required_conditions=sec_concerns,
            )
        )

        # 2. Architect evaluation
        arch_score = 0.85
        arch_vote = VoteType.APPROVE
        arch_conditions = []
        if any(w in p_low for w in ["rewrite all", "refactor whole", "delete everything"]):
            arch_score = 0.4
            arch_vote = VoteType.REJECT
            arch_conditions.append("High architectural blast radius; recommend incremental AST patching instead.")
        elif len(proposal) > 400:
            arch_score = 0.7
            arch_vote = VoteType.APPROVE_WITH_CONDITIONS
            arch_conditions.append("Decompose proposal into modular DAG tasks.")

        ballots.append(
            MemberBallot(
                role="Architect",
                vote=arch_vote,
                score=arch_score,
                rationale="Evaluated architectural modularity, blast radius, and design consistency.",
                required_conditions=arch_conditions,
            )
        )

        # 3. Pragmatist evaluation
        prag_score = 0.8
        prag_vote = VoteType.APPROVE
        prag_conditions = []
        if "docker" in p_low and "not installed" in c_low:
            prag_score = 0.3
            prag_vote = VoteType.REJECT
            prag_conditions.append("Dependency unavailable in environment; use native tempdir fallback.")
        ballots.append(
            MemberBallot(
                role="Pragmatist",
                vote=prag_vote,
                score=prag_score,
                rationale="Evaluated environment prerequisites, execution feasibility, and regression risks.",
                required_conditions=prag_conditions,
            )
        )

        # Calculate weighted consensus score
        total_score = sum(b.score * ConsensusEngine.WEIGHTS.get(b.role, 0.33) for b in ballots)
        has_rejection = any(b.vote == VoteType.REJECT for b in ballots)
        has_conditions = any(b.vote == VoteType.APPROVE_WITH_CONDITIONS for b in ballots)

        if has_rejection or total_score < 0.55:
            verdict = "REJECTED"
        elif has_conditions or total_score < 0.80:
            verdict = "APPROVED_WITH_CONDITIONS"
        else:
            verdict = "APPROVED"

        all_actions = []
        for b in ballots:
            all_actions.extend(b.required_conditions)

        memo = ConsensusMemo(
            proposal=proposal,
            verdict=verdict,
            consensus_score=round(total_score, 2),
            ballots=ballots,
            action_items=all_actions,
        )
        return memo
