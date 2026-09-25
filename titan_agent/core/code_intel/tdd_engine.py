"""
Phase 46 — Autonomous TDD Engine (Red-Green-Refactor Loop).

Guarantees high-integrity software engineering by enforcing strict Test-Driven Development:
1. RED: Writes a test first and executes it in isolation to prove it fails (asserting the requirement/bug).
2. GREEN: Writes the minimal implementation code and proves the test now passes.
3. REFACTOR & SYMBOLIC: Statically checks code invariants (no infinite loops, no shell injections)
   and verifies clean code structure before finalizing.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .symbolic_checker import SymbolicInvariantChecker

log = logging.getLogger(__name__)


@dataclass
class TDDStageResult:
    """Outcome of one TDD phase (RED, GREEN, or REFACTOR)."""

    stage: str  # "RED", "GREEN", "REFACTOR"
    success: bool
    output: str
    exit_code: int = 0
    duration_sec: float = 0.0


@dataclass
class TDDExecutionReport:
    """Full lifecycle report of an autonomous Red-Green-Refactor cycle."""

    test_name: str
    red_stage: TDDStageResult
    green_stage: TDDStageResult
    refactor_stage: TDDStageResult
    full_cycle_success: bool
    summary: str = ""

    def format_text(self) -> str:
        status_icon = "✅ PASSED" if self.full_cycle_success else "❌ FAILED"
        lines = [
            f"### AUTONOMOUS TDD CYCLE: {status_icon} [{self.test_name}]",
            f"1. **RED Phase (Failing Test)**: {'✓ Confirmed Failed' if self.red_stage.success else '✗ Unexpectedly Passed/Errored'}",
            f"   - Exit Code: {self.red_stage.exit_code} | Duration: {self.red_stage.duration_sec:.2f}s",
            f"2. **GREEN Phase (Implementation Fix)**: {'✓ Successfully Passed' if self.green_stage.success else '✗ Still Failing'}",
            f"   - Exit Code: {self.green_stage.exit_code} | Duration: {self.green_stage.duration_sec:.2f}s",
            f"3. **REFACTOR Phase (Symbolic Invariant)**: {'✓ Invariants Sound' if self.refactor_stage.success else '✗ Violations Detected'}",
            f"   - Invariant Status:\n{self.refactor_stage.output.strip()}",
        ]
        return "\n".join(lines)


class AutonomousTDDEngine:
    """Executes rigorous Red-Green-Refactor cycles in hermetic temp sandboxes."""

    def __init__(self, workspace_root: Path | str | None = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

    async def _run_pytest_in_dir(self, test_path: Path, cwd: Path, timeout: float = 30.0) -> tuple[int, str, float]:
        """Runs pytest on a test file and captures output."""
        start = asyncio.get_event_loop().time()
        cmd = [sys.executable, "-m", "pytest", str(test_path), "-v", "-s"]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            duration = asyncio.get_event_loop().time() - start
            out = stdout_bytes.decode("utf-8", errors="ignore")
            return proc.returncode or 0, out, duration
        except asyncio.TimeoutError:
            duration = asyncio.get_event_loop().time() - start
            return 124, f"Pytest timed out after {timeout}s", duration
        except Exception as exc:
            duration = asyncio.get_event_loop().time() - start
            return 1, f"Failed to execute pytest: {exc!s}", duration

    async def execute_tdd_cycle(
        self,
        test_code: str,
        implementation_code: str,
        test_filename: str = "test_feature.py",
        code_filename: str = "feature.py",
        timeout: float = 30.0,
    ) -> TDDExecutionReport:
        """Executes full RED -> GREEN -> REFACTOR validation in an isolated directory."""
        with tempfile.TemporaryDirectory(prefix="titan_tdd_") as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / test_filename
            code_file = tmppath / code_filename

            # -------------------------------------------------------------
            # Stage 1: RED PHASE (Test written, implementation absent/dummy)
            # -------------------------------------------------------------
            # Write dummy implementation or empty stub
            code_file.write_text("# Initial empty stub\n", encoding="utf-8")
            test_file.write_text(test_code, encoding="utf-8")

            red_code, red_out, red_dur = await self._run_pytest_in_dir(test_file, tmppath, timeout=timeout)
            # In TDD, the test MUST fail (exit code != 0) when the feature is not implemented
            red_success = red_code != 0
            red_stage = TDDStageResult(
                stage="RED",
                success=red_success,
                output=red_out,
                exit_code=red_code,
                duration_sec=red_dur,
            )

            # -------------------------------------------------------------
            # Stage 2: GREEN PHASE (Implementation written, test must pass)
            # -------------------------------------------------------------
            code_file.write_text(implementation_code, encoding="utf-8")
            green_code, green_out, green_dur = await self._run_pytest_in_dir(test_file, tmppath, timeout=timeout)
            green_success = green_code == 0
            green_stage = TDDStageResult(
                stage="GREEN",
                success=green_success,
                output=green_out,
                exit_code=green_code,
                duration_sec=green_dur,
            )

            # -------------------------------------------------------------
            # Stage 3: REFACTOR PHASE (Symbolic AST Invariant Verification)
            # -------------------------------------------------------------
            symbolic_report = SymbolicInvariantChecker.check_code(implementation_code)
            refactor_success = symbolic_report.is_safe
            refactor_stage = TDDStageResult(
                stage="REFACTOR",
                success=refactor_success,
                output=symbolic_report.summary(),
                exit_code=0 if refactor_success else 1,
                duration_sec=0.01,
            )

            full_success = red_success and green_success and refactor_success
            report = TDDExecutionReport(
                test_name=test_filename,
                red_stage=red_stage,
                green_stage=green_stage,
                refactor_stage=refactor_stage,
                full_cycle_success=full_success,
            )
            report.summary = report.format_text()
            return report
