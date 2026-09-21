"""
Phase 7 (Full Autonomy) — Self-Healing Loop.

When a command or tool fails, Titan no longer stops and asks: it *diagnoses*
the failure, applies the cheapest deterministic repair (install a missing
Python module, retry a flaky command, ...) and re-runs the original command
until it succeeds or the attempt budget is spent. Common repairs run entirely
locally (zero LLM tokens); anything exotic is left for the agent's own
reasoning loop to fix via the normal edit->re-run cycle.

The engine is a pure async function: give it an async "run" callable
(command -> (exit_code, stdout, stderr)) and it returns a full repair log.
"""
from __future__ import annotations

import re
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

# A run function: executes one command and returns (exit_code, stdout, stderr).
RunFn = Callable[[str], Awaitable[tuple[int, str, str]]]

# --- diagnostics ----------------------------------------------------------

_MODULE_NOT_FOUND = re.compile(
    r"ModuleNotFoundError:\s*No module named ['\"]([^'\"]+)['\"]"
)
_NUMPY_IMPORT = re.compile(r"numpy\.core\.multiarray")
_COMMAND_NOT_FOUND = re.compile(
    r"(not recognized as the name of a cmdlet|command not found|"
    r"is not recognized|No such file or directory)"
)
_MEMORY_ERROR = re.compile(r"MemoryError")


@dataclass
class Repair:
    """A single deterministic repair step that was applied."""

    kind: str
    label: str
    command: str | None = None


@dataclass
class HealResult:
    """The full outcome of a self-healing run."""

    command: str
    succeeded: bool = False
    attempts: list[dict[str, Any]] = field(default_factory=list)
    repairs: list[dict[str, Any]] = field(default_factory=list)
    final_stdout: str = ""
    final_stderr: str = ""
    final_code: int = 0

    def to_text(self) -> str:
        """Human-readable report for the agent / user."""
        lines = ["### SELF-HEAL REPORT"]
        lines.append(f"Command: {self.command}")
        lines.append(f"Status: {'SUCCESS' if self.succeeded else 'FAILED'}")
        lines.append(f"Attempts made: {len(self.attempts)}")
        if self.repairs:
            lines.append("Repairs applied:")
            for r in self.repairs:
                lines.append(f"- [{r['kind']}] {r['label']}")
        if self.final_stderr:
            lines.append(f"Final stderr:\n{self.final_stderr.strip()[:2000]}")
        if self.final_stdout:
            lines.append(f"Final stdout:\n{self.final_stdout.strip()[:2000]}")
        return "\n".join(lines)


def diagnose(stderr: str, stdout: str = "") -> Repair | None:
    """Classify a failure into a deterministic repair, or None if no local fix exists."""
    text = (stderr or "") + "\n" + (stdout or "")

    # numpy migrated its C core; `numpy.core` references in third-party code
    # are fixed by upgrading numpy, not by 'pip install core'.
    if _NUMPY_IMPORT.search(text):
        return Repair(
            kind="pip_install",
            label="numpy too old for the importing code — upgrading numpy",
            command=f'"{sys.executable}" -m pip install --quiet --upgrade numpy',
        )

    m = _MODULE_NOT_FOUND.search(text)
    if m:
        pkg = m.group(1).strip()
        return Repair(
            kind="pip_install",
            label=f"missing module '{pkg}' — installing it",
            command=f'"{sys.executable}" -m pip install --quiet {pkg}',
        )

    if _COMMAND_NOT_FOUND.search(text):
        return Repair(
            kind="retry",
            label="command lookup failed (flaky/transient) — retrying once",
        )

    if _MEMORY_ERROR.search(text):
        return Repair(
            kind="retry",
            label="MemoryError (transient pressure) — retrying once",
        )

    return None


async def heal_run(
    run: RunFn,
    command: str,
    max_attempts: int = 3,
) -> HealResult:
    """Run `command` via `run`; on failure, repair deterministically and retry.

    `run` is an async callable: command -> (exit_code, stdout, stderr).
    Returns a :class:`HealResult` with the full attempt and repair log.
    """
    result = HealResult(command=command)
    attempts = max(1, int(max_attempts or 1))

    for i in range(attempts):
        code, out, err = await run(command)
        result.attempts.append(
            {"attempt": i + 1, "exit_code": code, "stdout": out, "stderr": err}
        )
        if code == 0:
            result.succeeded = True
            result.final_code = 0
            result.final_stdout = out
            result.final_stderr = err
            return result

        last_err = err or out
        repair = diagnose(last_err)
        if repair is None:
            # No deterministic fix exists — leave it for the agent's reasoning loop.
            result.final_code = code
            result.final_stdout = out
            result.final_stderr = err
            return result

        result.repairs.append(
            {"kind": repair.kind, "label": repair.label, "command": repair.command}
        )
        if repair.command:
            # Apply the repair (its own exit code is best-effort — even a failed
            # install is worth one re-run of the original command in case the
            # package was already resolvable).
            await run(repair.command)

    # Budget exhausted without success.
    result.final_code = code
    result.final_stdout = out
    result.final_stderr = err
    return result


class SelfHealEngine:
    """Object wrapper around :func:`heal_run` for use as a tool handler."""

    def __init__(self, run: RunFn | None = None):
        self._run = run

    async def heal(
        self,
        command: str,
        max_attempts: int = 3,
        run: RunFn | None = None,
    ) -> HealResult:
        runner = run or self._run
        if runner is None:
            raise RuntimeError("SelfHealEngine has no run function")
        return await heal_run(runner, command, max_attempts=max_attempts)