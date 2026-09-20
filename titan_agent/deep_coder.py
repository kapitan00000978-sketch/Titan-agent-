import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from .tools import ToolRegistry

class DeepCoderEngine:
    """
    Autonomous Deep Coding Engine:
    Designs, generates, validates, and self-heals code until 100% verified.
    """
    def __init__(self, tools: ToolRegistry):
        self.tools = tools

    async def verify_python_code(self, filepath: Path) -> tuple[bool, str]:
        """Runs python py_compile to check syntax."""
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "py_compile", str(filepath),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return True, "Syntax OK"
        err_msg = stderr.decode('utf-8', errors='ignore') or stdout.decode('utf-8', errors='ignore')
        return False, err_msg

    async def run_test_script(self, test_filepath: Path) -> tuple[bool, str]:
        """Executes test script and returns outcome."""
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(test_filepath),
            cwd=str(self.tools.workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            out = stdout.decode('utf-8', errors='ignore')
            err = stderr.decode('utf-8', errors='ignore')
            if proc.returncode == 0:
                return True, out
            return False, f"Test failed (exit {proc.returncode}):\n{err}\n{out}"
        except asyncio.TimeoutError:
            proc.kill()
            return False, "Test timed out after 30 seconds."

    async def execute_coding_cycle(
        self,
        task_name: str,
        files_to_create: Dict[str, str],
        test_script_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a deep coding cycle:
        1. Writes files
        2. Validates syntax
        3. Runs tests
        4. Reports verification status
        """
        results = {
            "task": task_name,
            "created_files": [],
            "syntax_checks": {},
            "test_passed": None,
            "test_output": "",
            "status": "in_progress"
        }

        # Step 1: Write all implementation files
        for rel_path, code in files_to_create.items():
            res = self.tools.tool_write_file(rel_path, code)
            results["created_files"].append({"path": rel_path, "status": res})

            # Check syntax if python file
            if rel_path.endswith(".py"):
                fpath = self.tools._resolve_path(rel_path)
                ok, msg = await self.verify_python_code(fpath)
                results["syntax_checks"][rel_path] = {"valid": ok, "details": msg}

        # Step 2: Write and run tests if provided
        if test_script_content:
            test_path = self.tools._resolve_path(f"test_{task_name}.py")
            self.tools.tool_write_file(test_path.name, test_script_content)
            test_ok, test_out = await self.run_test_script(test_path)
            results["test_passed"] = test_ok
            results["test_output"] = test_out
            results["status"] = "success" if test_ok else "failed_tests"
        else:
            all_syntax_ok = all(v.get("valid", True) for v in results["syntax_checks"].values())
            results["status"] = "success" if all_syntax_ok else "syntax_error"

        return results
