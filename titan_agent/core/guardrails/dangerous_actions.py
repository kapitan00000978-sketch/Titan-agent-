"""
Dangerous Action Classifier & Human-in-the-Loop Interceptor.

Detects high-risk, destructive, or irreversible operations (e.g., file deletes,
git push --force, sensitive config overwrites, database truncations) and intercepts
them with human approval prompts before execution.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .hitl import ApprovalRequest, ApprovalStatus, HumanInTheLoop


@dataclass
class RiskAssessment:
    """Outcome of risk assessment for an intended agent action."""

    is_dangerous: bool
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    category: str
    reason: str
    suggested_prompt: str


class DangerousActionClassifier:
    """Analyzes actions, commands, and file paths to identify destructive operations."""

    DESTRUCTIVE_COMMAND_PATTERNS = [
        (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f?|-f)\b", "CRITICAL", "recursive_file_deletion", "Recursive deletion of files/directories"),
        (r"\bgit\s+push\s+.*(-f|--force)\b", "CRITICAL", "git_force_push", "Force pushing to remote repository overwriting history"),
        (r"\bgit\s+reset\s+--hard\b", "HIGH", "git_hard_reset", "Hard reset discarding uncommitted changes"),
        (r"\bgit\s+clean\s+(-[a-zA-Z]*f)\b", "HIGH", "git_clean_force", "Force cleaning untracked files"),
        (r"\b(format\s+[a-zA-Z]:|mkfs\b|dd\s+if=)\b", "CRITICAL", "disk_formatting", "Low-level filesystem formatting or raw block write"),
        (r"\bdrop\s+(database|table)\b", "CRITICAL", "database_destruction", "Dropping database or table structures"),
        (r"\btruncate\s+table\b", "HIGH", "database_truncation", "Truncating database table data"),
    ]

    SENSITIVE_FILES_PATTERNS = [
        r"(^|/|\\)\.env($|\.)",
        r"(^|/|\\)credentials(\.json|\.yaml|\.txt)?$",
        r"(^|/|\\)id_rsa($|\.)",
        r"(^|/|\\).*\.(pem|key|pfx|p12)$",
        r"(^|/|\\)production\.(json|yaml|yml|env)$",
    ]

    @classmethod
    def assess_action(cls, action: str, resource: str = "", details: dict[str, Any] | None = None) -> RiskAssessment:
        """Evaluates whether an action requires explicit Human-in-the-Loop consent."""
        details = details or {}
        command = str(details.get("command", "") or details.get("cmd", "") or "")
        path = str(resource or details.get("path", "") or details.get("file", "") or "")

        # Check command string for destructive patterns
        if command:
            for pattern, level, category, desc in cls.DESTRUCTIVE_COMMAND_PATTERNS:
                if re.search(pattern, command, re.IGNORECASE):
                    prompt = (
                        f"I am about to execute: {category} (`{command[:100]}`). "
                        "This may cause irreversible changes to your system or repository. "
                        "Do you authorize this action? [Yes / No]"
                    )
                    return RiskAssessment(
                        is_dangerous=True,
                        risk_level=level,
                        category=category,
                        reason=desc,
                        suggested_prompt=prompt,
                    )

        # Check file mutations for sensitive targets
        if action in ("write_file", "edit_file", "delete_file", "ast_replace_function"):
            for pat in cls.SENSITIVE_FILES_PATTERNS:
                if re.search(pat, path, re.IGNORECASE):
                    prompt = (
                        f"I am about to modify sensitive configuration file (`{path}`). "
                        "Do you authorize this action? [Yes / No]"
                    )
                    return RiskAssessment(
                        is_dangerous=True,
                        risk_level="HIGH",
                        category="sensitive_file_modification",
                        reason=f"Attempting to modify protected file: {path}",
                        suggested_prompt=prompt,
                    )

        if action == "delete_file":
            prompt = f"I am about to permanently delete this file (`{path}`). Do you authorize this action? [Yes / No]"
            return RiskAssessment(
                is_dangerous=True,
                risk_level="HIGH",
                category="file_deletion",
                reason=f"Permanent file deletion of {path}",
                suggested_prompt=prompt,
            )

        return RiskAssessment(
            is_dangerous=False,
            risk_level="LOW",
            category="standard",
            reason="Action is within standard operational boundaries.",
            suggested_prompt="",
        )


class DangerousActionGate:
    """Interception gate that blocks execution until human decides."""

    def __init__(self, hitl: HumanInTheLoop | None = None):
        self.hitl = hitl or HumanInTheLoop()

    async def check_and_gate(
        self,
        action: str,
        resource: str = "*",
        details: dict[str, Any] | None = None,
        timeout: float = 120.0,
    ) -> tuple[bool, str]:
        """
        Assesses action. If dangerous, requests human approval.
        Returns (is_approved, message).
        """
        details = details or {}
        assessment = DangerousActionClassifier.assess_action(action, resource, details)

        if not assessment.is_dangerous:
            return True, "Approved (Safe operation)"

        # Action is dangerous -> trigger approval request
        req = self.hitl.request(
            action=action,
            resource=resource,
            details=details,
            reason=f"[{assessment.risk_level}] {assessment.reason}: {assessment.suggested_prompt}",
        )

        try:
            decided_req = await self.hitl.wait(req, timeout=timeout)
            if decided_req.status == ApprovalStatus.APPROVED:
                return True, f"Operation approved by human ({decided_req.decided_by or 'user'})."
            elif decided_req.status == ApprovalStatus.TIMED_OUT:
                return False, f"Operation rejected: Approval timed out after {timeout}s without human confirmation."
            else:
                return False, f"Operation denied by human: {assessment.reason}."
        except Exception as exc:
            return False, f"Approval gate error: {exc!s}"
