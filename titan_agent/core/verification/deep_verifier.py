"""
Deep Test-Driven Verification Loop (Phase 45)

Mimics the robust autonomous iteration of models like DeepSeek R1 and Claude Code.
Given a piece of generated code, the verifier:
1. Generates a robust unit test suite for it.
2. Runs the tests inside the isolated Docker sandbox.
3. If tests fail, it parses the failure, determines the flaw, and feeds the error
   back into the reasoning loop for autonomous self-healing.
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from ..reasoning.interfaces import ILLMProvider, complete_text

TEST_GENERATION_PROMPT = """You are a rigorous Test-Driven Development (TDD) engine.
Given the target code and its original intent, generate a comprehensive, robust 
Python unit test file using `pytest` that thoroughly exercises the logic, edge cases, 
and potential failure modes.

Original Intent:
{intent}

Target Code:
{code}

Respond with EXACTLY and ONLY the raw Python code for the test file (no markdown code blocks, no explanations).
The code MUST be importable and runnable by pytest.
"""


class DeepVerifier:
    def __init__(self, llm: ILLMProvider, sandbox_runner: Callable[[str], Awaitable[str]] | None = None):
        self.llm = llm
        self.sandbox_runner = sandbox_runner

    async def generate_tests(self, code: str, intent: str) -> str:
        """Autonomously generate a unit test suite for the target code."""
        prompt = TEST_GENERATION_PROMPT.format(intent=intent, code=code)
        raw_test_code = await complete_text(
            self.llm,
            messages=[
                {"role": "system", "content": "You output raw Python code only. No markdown formatting."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=3000,
        )
        # Strip markdown fences if the LLM hallucinated them
        clean_code = raw_test_code.strip()
        if clean_code.startswith("```"):
            lines = clean_code.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_code = "\n".join(lines).strip()
        return clean_code

    async def verify_in_sandbox(self, target_code: str, test_code: str) -> dict[str, Any]:
        """
        Runs the target code and its tests in the Docker sandbox.
        Returns a dict with 'success', 'stdout', 'stderr'.
        """
        # We prepare a small shell script to create the files and run pytest
        script = f"""
cat << 'EOF' > target.py
{target_code}
EOF

cat << 'EOF' > test_target.py
import target
{test_code.replace('from target import', 'import target\\n# ')}
EOF

python -m pytest test_target.py -v
"""
        # Run inside sandbox
        if self.sandbox_runner:
            result_json = await self.sandbox_runner(script)
        else:
            result_json = '{"exit_code": 1, "stdout": "", "stderr": "sandbox_runner not configured"}'
            
        try:
            result = json.loads(result_json)
        except (json.JSONDecodeError, ValueError):
            return {"success": False, "stdout": "", "stderr": result_json, "exit_code": -1}
            
        success = result.get("exit_code") == 0
        return {
            "success": success,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code", -1)
        }

    async def self_heal_loop(
        self,
        code: str,
        intent: str,
        max_iterations: int = 3
    ) -> dict[str, Any]:
        """
        The deep verification loop.
        Generates tests -> Runs tests -> If fail, ask LLM to fix code based on stderr -> Repeat.
        Returns the final verified code and status.
        """
        current_code = code
        test_code = await self.generate_tests(current_code, intent)
        
        for iteration in range(max_iterations):
            run_result = await self.verify_in_sandbox(current_code, test_code)
            if run_result["success"]:
                return {
                    "verified": True,
                    "code": current_code,
                    "test_code": test_code,
                    "iterations": iteration + 1,
                    "final_output": run_result["stdout"]
                }
                
            # If failed, heal the code
            heal_prompt = f"""The generated code failed its unit tests.
Original Intent: {intent}

Current Code:
{current_code}

Test Code:
{test_code}

Test Execution Output (Error):
{run_result['stdout']}
{run_result['stderr']}

Analyze the error and provide the CORRECTED raw Python code for the target.
Respond with EXACTLY and ONLY the raw Python code (no markdown, no explanation).
"""
            raw_fixed = await complete_text(
                self.llm,
                messages=[
                    {"role": "system", "content": "You output raw Python code only. No markdown formatting."},
                    {"role": "user", "content": heal_prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
            )
            clean_fixed = raw_fixed.strip()
            if clean_fixed.startswith("```"):
                lines = clean_fixed.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_fixed = "\n".join(lines).strip()
            current_code = clean_fixed

        return {
            "verified": False,
            "code": current_code,
            "test_code": test_code,
            "iterations": max_iterations,
            "final_output": "Exhausted iteration budget without tests passing."
        }
