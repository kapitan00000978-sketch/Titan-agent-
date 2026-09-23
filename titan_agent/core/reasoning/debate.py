"""
Phase 24 — Level 4: Multi-Agent Debate Engine.

Pits two opposing agents (Advocate/Proposer and Skeptic/Challenger) against each other
to stress-test architectural decisions, design trade-offs, and critical system changes.
A neutral Judge/Arbitrator evaluates the debate transcript and delivers an authoritative,
compromise-aware consensus verdict.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from .interfaces import ILLMProvider, complete_text

PROPOSER_PROMPT = """You are the LEAD ARCHITECT & ADVOCATE in a technical debate.
Topic: {topic}

Present the strongest, most compelling argument, concrete solution, and benefits for your proposal.
Focus on scalability, elegance, efficiency, and real-world viability.
"""

PROPOSER_REBUTTAL = """You are the LEAD ARCHITECT & ADVOCATE in Round {round_num}.
Topic: {topic}

The Challenger has raised the following counter-arguments:
{challenger_argument}

Defend your architecture:
1. Directly address and refute invalid criticisms.
2. Concede genuine trade-offs and explain how you mitigate them.
3. Reaffirm why your approach is optimal.
"""

CHALLENGER_PROMPT = """You are the ADVERSARIAL SKEPTIC & SECURITY AUDITOR in a technical debate.
Topic: {topic}

The Proposer argues:
{proposer_argument}

Relentlessly challenge this approach:
1. Identify hidden edge cases, failure modes, and security risks.
2. Point out operational complexity, maintenance overhead, and latency costs.
3. Propose a counter-alternative or highlight why the proposal fails under stress.
"""

JUDGE_PROMPT = """You are the CHIEF TECHNOLOGY JUDGE & ARBITRATOR.
Topic: {topic}

Review the following multi-round technical debate between the Advocate (Proposer) and Skeptic (Challenger):

DEBATE TRANSCRIPT:
{transcript}

Deliver an authoritative, balanced final verdict.
Respond with valid JSON ONLY:
{{
  "winner": "PROPOSER" | "CHALLENGER" | "HYBRID_CONSENSUS",
  "recommended_architecture": "Concise statement of the winning decision",
  "judge_rationale": "Why this approach won and how the valid criticisms are addressed",
  "tradeoffs_accepted": ["List of trade-offs explicitly accepted"],
  "final_action_plan": "Concrete, step-by-step recommendation for the engineering team"
}}
"""


@dataclass
class DebateTurn:
    speaker: str  # "proposer", "challenger", "judge"
    round_num: int
    argument: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class DebateResult:
    topic: str
    winner: str
    recommended_architecture: str
    judge_rationale: str
    tradeoffs_accepted: list[str]
    final_action_plan: str
    turns: list[DebateTurn] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "# MULTI-AGENT DEBATE OUTCOME",
            f"**Topic**: {self.topic}",
            f"**Verdict**: {self.winner}",
            f"**Decision**: {self.recommended_architecture}",
            "",
            "### Judge Rationale:",
            self.judge_rationale,
            "",
            "### Trade-offs Accepted:",
        ]
        for to in self.tradeoffs_accepted:
            lines.append(f"- {to}")
        lines.extend([
            "",
            "### Final Action Plan:",
            self.final_action_plan,
        ])
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "winner": self.winner,
            "recommended_architecture": self.recommended_architecture,
            "judge_rationale": self.judge_rationale,
            "tradeoffs_accepted": self.tradeoffs_accepted,
            "final_action_plan": self.final_action_plan,
            "transcript": [
                {
                    "speaker": t.speaker,
                    "round": t.round_num,
                    "argument": t.argument,
                }
                for t in self.turns
            ],
        }


class DebateEngine:
    """Executes a multi-round debate between Proposer and Challenger with Judge arbitration."""

    def __init__(self, llm: ILLMProvider):
        self.llm = llm

    async def run_debate(self, topic: str, rounds: int = 2) -> DebateResult:
        turns: list[DebateTurn] = []
        max_rounds = max(1, min(rounds, 3))

        last_proposer_arg = ""
        last_challenger_arg = ""

        for r in range(1, max_rounds + 1):
            # Proposer turn
            if r == 1:
                prompt_p = PROPOSER_PROMPT.format(topic=topic)
            else:
                prompt_p = PROPOSER_REBUTTAL.format(
                    round_num=r,
                    topic=topic,
                    challenger_argument=last_challenger_arg,
                )

            last_proposer_arg = await complete_text(
                self.llm,
                messages=[
                    {"role": "system", "content": "You are the Advocate Lead Architect. Make compelling technical points."},
                    {"role": "user", "content": prompt_p},
                ],
                temperature=0.3,
            )
            turns.append(DebateTurn(speaker="proposer", round_num=r, argument=last_proposer_arg))

            # Challenger turn
            prompt_c = CHALLENGER_PROMPT.format(topic=topic, proposer_argument=last_proposer_arg)
            last_challenger_arg = await complete_text(
                self.llm,
                messages=[
                    {"role": "system", "content": "You are the Skeptic Security Auditor. Relentlessly challenge assumptions."},
                    {"role": "user", "content": prompt_c},
                ],
                temperature=0.3,
            )
            turns.append(DebateTurn(speaker="challenger", round_num=r, argument=last_challenger_arg))

        # Judge Arbitration
        transcript_text = "\n\n".join(
            f"--- {t.speaker.upper()} (Round {t.round_num}) ---\n{t.argument}" for t in turns
        )
        prompt_j = JUDGE_PROMPT.format(topic=topic, transcript=transcript_text)
        judge_raw = await complete_text(
            self.llm,
            messages=[
                {"role": "system", "content": "You are the impartial Chief Technology Judge. Output valid JSON only."},
                {"role": "user", "content": prompt_j},
            ],
            temperature=0.1,
        )

        judge_data = self._parse_judge_json(judge_raw)
        turns.append(
            DebateTurn(
                speaker="judge",
                round_num=max_rounds + 1,
                argument=json.dumps(judge_data, indent=2),
            )
        )

        return DebateResult(
            topic=topic,
            winner=judge_data.get("winner", "HYBRID_CONSENSUS"),
            recommended_architecture=judge_data.get("recommended_architecture", topic),
            judge_rationale=judge_data.get("judge_rationale", "Both sides presented valid points."),
            tradeoffs_accepted=judge_data.get("tradeoffs_accepted", []),
            final_action_plan=judge_data.get("final_action_plan", "Proceed with balanced implementation."),
            turns=turns,
        )

    def _parse_judge_json(self, raw: str) -> dict[str, Any]:
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end > start:
                return json.loads(raw[start : end + 1])
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        return {
            "winner": "HYBRID_CONSENSUS",
            "recommended_architecture": "Balanced architecture incorporating both advocate and skeptic recommendations.",
            "judge_rationale": raw[:300] if raw else "Arbitration synthesized best aspects of both positions.",
            "tradeoffs_accepted": ["Performance vs complexity balance"],
            "final_action_plan": "Adopt proposal with added safety checks and monitoring.",
        }
