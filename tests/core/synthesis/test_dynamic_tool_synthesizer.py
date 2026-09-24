"""Unit tests for DynamicToolSynthesizer."""
import asyncio
import pytest
from pathlib import Path
from titan_agent.core.synthesis.dynamic_tool_synthesizer import (
    DynamicToolSynthesizer,
    SynthesizedToolSpec,
)


@pytest.mark.asyncio
async def test_validate_syntax():
    synth = DynamicToolSynthesizer()
    ok, msg = synth.validate_syntax("def foo(x):\n    return x + 1\n")
    assert ok is True
    assert "foo" in msg

    bad_ok, bad_msg = synth.validate_syntax("def broken(:")
    assert bad_ok is False
    assert "SyntaxError" in bad_msg


@pytest.mark.asyncio
async def test_sandbox_testing(tmp_path):
    synth = DynamicToolSynthesizer(workspace_root=tmp_path)
    tool_code = "def add_two(x):\n    return x + 2\n"
    test_code = "assert synthesized_module.add_two(3) == 5"

    passed, out = await synth.test_in_isolated_sandbox(tool_code, test_code)
    assert passed is True
    assert "Sandbox test passed" in out

    failing_test = "assert synthesized_module.add_two(3) == 999"
    fail_passed, fail_out = await synth.test_in_isolated_sandbox(tool_code, failing_test)
    assert fail_passed is False
    assert "AssertionError" in fail_out


@pytest.mark.asyncio
async def test_synthesize_and_register(tmp_path):
    class FakeRegistry:
        def __init__(self):
            self.workspace = tmp_path

    reg = FakeRegistry()
    synth = DynamicToolSynthesizer(workspace_root=tmp_path)

    tool_code = (
        "async def custom_hash(text: str) -> str:\n"
        "    return f'HASH_{len(text)}_{text[::-1]}'\n"
    )
    test_code = (
        "res = asyncio.run(synthesized_module.custom_hash('hello'))\n"
        "assert res == 'HASH_5_olleh'\n"
    )

    ok, msg = await synth.synthesize_and_register(
        name="custom_hash",
        description="Reverses string and computes length hash",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        python_code=tool_code,
        test_code=test_code,
        registry=reg,
    )

    assert ok is True
    assert hasattr(reg, "tool_custom_hash")
    # Verify tool callable works
    result = await reg.tool_custom_hash("titan")
    assert result == "HASH_5_natit"
    assert "custom_hash" in reg._synthesized_definitions
