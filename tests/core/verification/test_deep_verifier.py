import pytest
from unittest.mock import patch, MagicMock
from titan_agent.core.verification.deep_verifier import DeepVerifier
from titan_agent.core.reasoning.interfaces import ILLMProvider
from typing import Any

class DummyLLM(ILLMProvider):
    async def complete(self, messages, **kwargs) -> Any:
        return type('Response', (), {'content': 'def test_foo():\n    assert True', 'tool_calls': []})()
        
    async def complete_with_tools(self, messages, tools, **kwargs) -> Any:
        return await self.complete(messages, **kwargs)

@pytest.mark.asyncio
async def test_deep_verifier_generate_tests():
    llm = DummyLLM()
    verifier = DeepVerifier(llm)
    
    test_code = await verifier.generate_tests("def foo(): return True", "A foo function")
    assert "def test_foo():" in test_code
    assert "assert True" in test_code

@pytest.mark.asyncio
async def test_deep_verifier_sandbox_success():
    async def mock_sandbox(script):
        return '{"exit_code": 0, "stdout": "1 passed", "stderr": ""}'
        
    llm = DummyLLM()
    verifier = DeepVerifier(llm, sandbox_runner=mock_sandbox)
    
    result = await verifier.verify_in_sandbox("def foo(): pass", "def test_foo(): pass")
    assert result["success"] is True
    assert result["exit_code"] == 0

@pytest.mark.asyncio
async def test_deep_verifier_heal_loop():
    # Mocking first failure, second success
    calls = []
    async def mock_sandbox(script):
        calls.append(script)
        if len(calls) == 1:
            return '{"exit_code": 1, "stdout": "failed", "stderr": "error"}'
        return '{"exit_code": 0, "stdout": "passed", "stderr": ""}'
    
    llm = DummyLLM()
    verifier = DeepVerifier(llm, sandbox_runner=mock_sandbox)
    
    result = await verifier.self_heal_loop("def foo(): return False", "foo function")
    assert result["verified"] is True
    assert result["iterations"] == 2
