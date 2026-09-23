import pytest
import asyncio
from typing import Any
from titan_agent.core.reasoning.mcts import MCTSEngine, MCTSNode
from titan_agent.core.reasoning.types import ReasoningTrace, ReasoningStep, ActionType, StepStatus
from titan_agent.core.reasoning.interfaces import IEvaluator, ILLMProvider

class DummyLLM(ILLMProvider):
    async def complete(self, messages, **kwargs) -> Any:
        return type('Response', (), {'content': '["idea A", "idea B"]', 'tool_calls': []})()
        
    async def complete_with_tools(self, messages, tools, **kwargs) -> Any:
        return await self.complete(messages, **kwargs)

class DummyEvaluator(IEvaluator):
    async def evaluate(self, trace, candidates) -> list[float]:
        return [0.8] * len(candidates)
        
    async def is_solution(self, trace, goal) -> tuple[bool, float]:
        last = trace.get_last_step()
        if last and "idea A" in last.content:
            return True, 0.9
        return False, 0.0

@pytest.mark.asyncio
async def test_mcts_reasoning_flow():
    llm = DummyLLM()
    evaluator = DummyEvaluator()
    engine = MCTSEngine(llm=llm, evaluator=evaluator)
    
    trace = await engine.reason("Solve this test")
    
    assert trace is not None
    assert trace.final_answer is not None
    assert trace.completed_at is not None

@pytest.mark.asyncio
async def test_mcts_node_uct():
    trace = ReasoningTrace(task="Test")
    node = MCTSNode(state=trace)
    
    # 0 visits should return inf
    assert node.uct_score() == float('inf')
    
    node.visits = 1
    node.value = 1.0
    
    # Without parent, it calculates UCT using its own visits for log
    uct = node.uct_score()
    assert uct > 0.0
