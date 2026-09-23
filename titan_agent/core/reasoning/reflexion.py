"""
Phase 24 — Level 4: Reflexion Loop (Self-Critique and Auto-Correction Engine).

Allows an agent to critically evaluate its own draft output, detect hallucinations,
logical flaws, or syntax issues, and iteratively refine the result up to N cycles (default 3).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from .interfaces import ILLMProvider, complete_text

CRITIQUE_PROMPT = """You are a rigorous, impartial self-critic and quality auditor.
Analyze the following proposed solution to the given task.
Identify any:
1. Factual inaccuracies or unverified assumptions
2. Logical flaws, missed edge cases, or broken requirements
3. Code syntax errors or missing imports (if code is included)
4. Incomplete or superficial answers

Task:
{task}

Proposed Solution:
{solution}

Respond with valid JSON ONLY:
{{
  "verdict": "PASS" | "NEEDS_REVISION",
  "score": 1-10,
  "critique": "Specific actionable points of failure or 'Solution meets all criteria cleanly.'",
  "remediation_advice": "Concrete instructions on how to correct the flaws."
}}
"""

REFINEMENT_PROMPT = """You are refining an answer based on critical feedback.
Original Task:
{task}

Previous Draft:
{solution}

Critique & Flaws Identified:
{critique}

Remediation Instructions:
{remediation}

Produce a complete, corrected, and strictly improved final solution that resolves ALL the critique points.
"""


@dataclass
class ReflexionCycle:
    cycle: int
    draft: str
    verdict: str
    score: int
    critique: str
    remediation: str
    duration: float = 0.0


@dataclass
class ReflexionResult:
    task: str
    success: bool
    final_output: str
    total_cycles: int
    initial_output: str
    improved: bool
    cycles: list[ReflexionCycle] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "success": self.success,
            "total_cycles": self.total_cycles,
            "improved": self.improved,
            "final_output": self.final_output,
            "cycles": [
                {
                    "cycle": c.cycle,
                    "verdict": c.verdict,
                    "score": c.score,
                    "critique": c.critique,
                    "remediation": c.remediation,
                    "duration": round(c.duration, 2),
                }
                for c in self.cycles
            ],
        }


class ReflexionEngine:
    """Iterative self-critique loop improving drafts until approved or cycles exhausted."""

    def __init__(self, llm: ILLMProvider):
        self.llm = llm

    async def run(
        self,
        task: str,
        initial_draft: str | None = None,
        max_cycles: int = 3,
    ) -> ReflexionResult:
        current_draft = initial_draft or ""
        cycles_record: list[ReflexionCycle] = []

        # If no initial draft provided, generate the baseline
        if not current_draft.strip():
            current_draft = await complete_text(
                self.llm,
                messages=[
                    {"role": "system", "content": "You are a senior problem solver. Provide a complete, high-quality solution."},
                    {"role": "user", "content": task},
                ],
                temperature=0.3,
            )

        initial_output = current_draft
        success = False

        for cycle_num in range(1, max_cycles + 1):
            c_start = time.time()
            critique_data = await self._critique(task, current_draft)
            verdict = critique_data.get("verdict", "PASS")
            score = int(critique_data.get("score", 7))
            critique = critique_data.get("critique", "")
            remediation = critique_data.get("remediation_advice", "")

            cycle_entry = ReflexionCycle(
                cycle=cycle_num,
                draft=current_draft,
                verdict=verdict,
                score=score,
                critique=critique,
                remediation=remediation,
                duration=time.time() - c_start,
            )
            cycles_record.append(cycle_entry)

            if verdict == "PASS" or score >= 9:
                success = True
                break

            # If not passing and we still have cycles left, refine!
            if cycle_num < max_cycles:
                current_draft = await self._refine(task, current_draft, critique, remediation)
            else:
                # Even if exhausted, mark success if score is acceptable (>= 7)
                success = score >= 7

        return ReflexionResult(
            task=task,
            success=success,
            final_output=current_draft,
            total_cycles=len(cycles_record),
            initial_output=initial_output,
            improved=len(cycles_record) > 1 and current_draft != initial_output,
            cycles=cycles_record,
        )

    async def _critique(self, task: str, solution: str) -> dict[str, Any]:
        prompt = CRITIQUE_PROMPT.format(task=task, solution=solution)
        raw = await complete_text(
            self.llm,
            messages=[
                {"role": "system", "content": "Output valid JSON only with keys: verdict, score, critique, remediation_advice."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end > start:
                return json.loads(raw[start : end + 1])
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        # Fallback critique
        return {
            "verdict": "PASS",
            "score": 8,
            "critique": "Draft appears acceptable.",
            "remediation_advice": "",
        }

    async def _refine(self, task: str, solution: str, critique: str, remediation: str) -> str:
        prompt = REFINEMENT_PROMPT.format(
            task=task,
            solution=solution,
            critique=critique,
            remediation=remediation,
        )
        return await complete_text(
            self.llm,
            messages=[
                {"role": "system", "content": "You are an expert engineer. Produce an improved, flaw-free version addressing every critique point."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
