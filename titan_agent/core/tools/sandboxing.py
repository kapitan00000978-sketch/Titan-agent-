"""
Phase 26 — Genesis Darajasi 8: Tool Sandboxing & Execution Guard.

Enforces execution isolation on HIGH_RISK tools (filesystem destruction,
raw process manipulation, network downloads) depending on active sandbox mode.
"""
from __future__ import annotations

import os
from enum import Enum
from typing import Any, ClassVar

from .registry import RiskLevel


class SandboxMode(str, Enum):
    OFF = "off"
    STRICT = "strict"
    DOCKER = "docker"


class ToolSandboxGuard:
    """Guards and enforces sandboxing isolation on tool invocations."""

    HIGH_RISK_TOOLS: ClassVar[set[str]] = {
        "execute_command",
        "self_heal",
        "manage_processes",
        "download_file",
        "window_control",
        "key_press",
        "mouse_click",
    }

    CONTROLLED_TOOLS: ClassVar[set[str]] = {
        "write_file",
        "apply_patch",
        "ast_patch_file",
        "skill_save",
        "git_commit",
    }

    def __init__(self, mode: SandboxMode | str | None = None):
        if mode is None:
            raw_mode = os.getenv("TITAN_TOOL_SANDBOX", "off").lower().strip()
            self.mode = SandboxMode(raw_mode) if raw_mode in ("off", "strict", "docker") else SandboxMode.OFF
        elif isinstance(mode, SandboxMode):
            self.mode = mode
        else:
            self.mode = SandboxMode(str(mode).lower().strip())

    def get_risk_level(self, tool_name: str) -> RiskLevel:
        """Categorize tool by risk level."""
        name = str(tool_name).strip()
        if name in self.HIGH_RISK_TOOLS:
            return RiskLevel.HIGH
        elif name in self.CONTROLLED_TOOLS:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def check_execution(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Validates if tool execution is permitted under current sandbox policy.
        Returns: (is_allowed, denial_or_warning_message)
        """
        risk = self.get_risk_level(tool_name)

        if self.mode == SandboxMode.OFF:
            return True, ""

        if self.mode == SandboxMode.STRICT and risk == RiskLevel.HIGH and not args.get("confirmed"):
            return (
                False,
                (
                    f"SANDBOX STRICT: Tool '{tool_name}' is classified as HIGH_RISK. "
                    "Execution denied unless 'confirmed=True' is explicitly provided."
                ),
            )

        if self.mode == SandboxMode.DOCKER and tool_name == "execute_command":
            cmd = str(args.get("command", ""))
            return (
                False,
                (
                    f"SANDBOX DOCKER: Raw host execution of '{cmd}' is blocked. "
                    "Use 'docker_sandbox_run' tool instead to run commands inside an isolated container."
                ),
            )

        return True, ""
