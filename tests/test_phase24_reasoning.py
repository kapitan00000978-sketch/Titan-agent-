"""
Tests for Phase 24 Genesis Level Reasoning Engines:
- Reflexion Loop (Self-Critique and Iterative Refinement)
- Multi-Agent Debate (Proposer vs Challenger with Judicial Arbitration)
- StructuredEngine strategy routing for reflexion and debate
- Tool integrations (debate_solve, reflexion_solve)
"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from titan_agent.core.reasoning.debate import DebateEngine
from titan_agent.core.reasoning.interfaces import ILLMProvider
from titan_agent.core.reasoning.reflexion import ReflexionEngine
from titan_agent.tools import ToolRegistry


class MockLLM(ILLMProvider):
    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or [])
        self.call_count = 0

    async def complete(self, messages, temperature=0.3, max_tokens=4096, stream=False):
        self.call_count += 1
        if self.responses:
            return self.responses.pop(0)
        return "Standard mock response"

    async def complete_with_tools(self, messages, tools, temperature=0.3, max_tokens=4096):
        return {"content": await self.complete(messages), "tool_calls": []}


@pytest.mark.asyncio
async def test_reflexion_clean_pass():
    """If the initial draft is high quality, reflexion passes on cycle 1."""
    critique_pass = json.dumps({
        "verdict": "PASS",
        "score": 10,
        "critique": "Solution meets all criteria cleanly.",
        "remediation_advice": "",
    })
    # response 1: draft, response 2: critique
    llm = MockLLM(["def add(a, b): return a + b", critique_pass])
    engine = ReflexionEngine(llm)

    res = await engine.run("Implement add function")
    assert res.success is True
    assert res.total_cycles == 1
    assert res.improved is False
    assert "add" in res.final_output


@pytest.mark.asyncio
async def test_reflexion_self_correction():
    """If cycle 1 has flaws, reflexion corrects itself on cycle 2."""
    draft_1 = "def divide(a, b): return a / b"
    critique_1 = json.dumps({
        "verdict": "NEEDS_REVISION",
        "score": 5,
        "critique": "Missing ZeroDivisionError handling.",
        "remediation_advice": "Check if b == 0 before dividing.",
    })
    draft_2 = "def divide(a, b):\n    if b == 0:\n        raise ValueError('Cannot divide by zero')\n    return a / b"
    critique_2 = json.dumps({
        "verdict": "PASS",
        "score": 10,
        "critique": "ZeroDivisionError handled cleanly.",
        "remediation_advice": "",
    })

    llm = MockLLM([draft_1, critique_1, draft_2, critique_2])
    engine = ReflexionEngine(llm)

    res = await engine.run("Implement divide function")
    assert res.success is True
    assert res.total_cycles == 2
    assert res.improved is True
    assert "Cannot divide by zero" in res.final_output
    assert res.cycles[0].verdict == "NEEDS_REVISION"
    assert res.cycles[1].verdict == "PASS"


@pytest.mark.asyncio
async def test_debate_engine():
    """Verify multi-round debate produces transcript and balanced judge arbitration."""
    prop_r1 = "Microservices allow independent scaling and rapid deployment."
    chal_r1 = "Microservices introduce massive network latency, distributed transaction complexity, and ops overhead."
    prop_r2 = "We mitigate latency with gRPC and event-driven architecture using Kafka."
    chal_r2 = "Kafka introduces operational burden that a small team cannot sustain."
    judge_json = json.dumps({
        "winner": "HYBRID_CONSENSUS",
        "recommended_architecture": "Modular monolith with clear service boundaries; extract services only when scaling dictates.",
        "judge_rationale": "Microservices premature complexity outweighs benefits, but modular structure allows future evolution.",
        "tradeoffs_accepted": ["Monolith deployment coupling in exchange for simplified ops"],
        "final_action_plan": "Start with modular monolith in a single repository.",
    })

    llm = MockLLM([prop_r1, chal_r1, prop_r2, chal_r2, judge_json])
    engine = DebateEngine(llm)

    res = await engine.run_debate("Monolith vs Microservices", rounds=2)
    assert res.winner == "HYBRID_CONSENSUS"
    assert "Modular monolith" in res.recommended_architecture
    assert len(res.turns) == 5  # 2 proposer + 2 challenger + 1 judge
    assert "MULTI-AGENT DEBATE OUTCOME" in res.summary()


@pytest.mark.asyncio
async def test_tools_debate_and_reflexion():
    """Verify debate_solve and reflexion_solve tools."""
    tools = ToolRegistry()

    # Mock LLM client on tools
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = json.dumps({
        "verdict": "PASS",
        "score": 9,
        "critique": "Clean",
        "remediation_advice": "",
    })
    mock_client.chat_completion = AsyncMock(return_value=mock_resp)
    tools._llm_client = mock_client

    ref_out = await tools.tool_reflexion_solve("Write binary search")
    assert "REFLEXION OUTCOME" in ref_out

    # Mock for debate
    judge_resp = MagicMock()
    judge_resp.content = json.dumps({
        "winner": "PROPOSER",
        "recommended_architecture": "PostgreSQL with JSONB",
        "judge_rationale": "ACID compliance needed",
        "tradeoffs_accepted": [],
        "final_action_plan": "Use Postgres",
    })
    mock_client.chat_completion = AsyncMock(return_value=judge_resp)

    deb_out = await tools.tool_debate_solve("Postgres vs MongoDB for financial transactions")
    assert "MULTI-AGENT DEBATE OUTCOME" in deb_out
    assert "PROPOSER" in deb_out
