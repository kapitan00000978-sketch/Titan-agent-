"""Blue Team Sentinel: Always-on continuous security monitoring and active defense."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ThreatLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class BlueTeamEvaluation:
    """Outcome of a Blue Team security evaluation."""
    allowed: bool = True
    threat_level: ThreatLevel = ThreatLevel.NONE
    threat_score: float = 0.0  # 0.0 (benign) -> 1.0 (imminent critical breach)
    reasons: list[str] = field(default_factory=list)
    threat_vector: str = "benign"
    is_emergency: bool = False
    details: dict[str, Any] = field(default_factory=dict)


class BlueTeamSentinel:
    """Always-On Blue Team Defense Engine.

    Continuously inspects incoming prompts, executed tool calls, command payloads,
    and generated code to enforce safety, block exploits, and safeguard the agent OS.
    """

    # Secret / credential exfiltration patterns
    SECRET_PATTERNS = [
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
        (r"ghp_[0-9a-zA-Z]{36}", "GitHub Personal Access Token"),
        (r"github_pat_[0-9a-zA-Z_]{82}", "GitHub Fine-Grained Token"),
        (r"sk-[a-zA-Z0-9_-]{32,}", "OpenAI/Anthropic API Key"),
        (r"-----BEGIN (RSA|EC|OPENSSH|PGP|PRIVATE) KEY-----", "Private Key / Certificate"),
        (r"(password|passwd|secret|api_key|token)\s*[:=]\s*['\"][^\s'\"]{8,}['\"]", "Hardcoded Secret Assignment"),
    ]

    # Malicious / lethal OS command patterns
    DANGEROUS_COMMAND_PATTERNS = [
        (r"(^|\s)(rm|del|rmdir)\s+(-[rfRF]+\s+|/s\s+/q\s+)?([\\/]|[a-zA-Z]:[\\/]|~|C:[\\/])($|\s)", "Root/Drive-level Destructive Deletion"),
        (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "Fork Bomb Denial-of-Service"),
        (r"(nc|ncat|netcat)\s+.*-[eec]\s+.*(sh|bash|cmd|powershell)", "Reverse Shell Execution (Netcat)"),
        (r"/dev/tcp/\d+\.\d+\.\d+\.\d+/\d+", "Direct /dev/tcp Reverse Shell"),
        (r"(mkfifo\s+/tmp/|mknod\s+/tmp/)", "Named Pipe Reverse Shell Setup"),
        (r"dd\s+if=/dev/(zero|urandom)\s+of=/dev/[a-z0-9]+", "Raw Disk Overwrite / Wipe"),
        (r"(format\s+[a-zA-Z]:|diskpart)", "Drive Formatting / Diskpart Utility"),
        (r"(curl|wget)\s+.*\|\s*(bash|sh|python|perl|powershell)", "Untrusted Remote Script Execution via Pipe"),
        (r"(mimikatz|pwdump|procdump\s+.*lsass)", "Credential Dumping Tool"),
        (r"(Invoke-Mimikatz|Invoke-ReflectivePEInjection)", "PowerSploit Offensive Tool"),
    ]

    # Prompt Injection & Adversarial Jailbreak Patterns
    INJECTION_PATTERNS = [
        (r"(ignore\s+(all\s+)?(previous|above|prior)\s+instructions)", "Prompt Injection: Instruction Override"),
        (r"(disregard\s+(all\s+)?(safety|system)\s+rules)", "Prompt Injection: Safety Disregard"),
        (r"(you\s+are\s+now\s+in\s+DAN\s+mode|Do\s+Anything\s+Now)", "Jailbreak: DAN Mode Persona"),
        (r"(\bprint\s+your\s+(system\s+prompt|initial\s+instructions)\b)", "Prompt Exfiltration Attempt"),
        (r"(\bSYSTEM\s+OVERRIDE:\s*DISABLE_ALL_RESTRICTIONS\b)", "Adversarial System Override Token"),
        (r"(\bbase64\s+decode\s+and\s+execute\s+as\s+root\b)", "Obfuscated Root Execution Request"),
    ]

    # Web & SSRF / Code Injection Patterns
    CODE_EXPLOIT_PATTERNS = [
        (r"169\.254\.169\.254", "SSRF: Cloud Instance Metadata Service Access"),
        (r"(\.\./){3,}", "Path Traversal Attack (Deep)"),
        (r"(UNION\s+ALL\s+SELECT|' OR '1'='1'|--\s*$|;\s*DROP\s+TABLE)", "SQL Injection Pattern"),
    ]

    def __init__(self):
        self._blocked_count = 0
        self._threat_history: list[BlueTeamEvaluation] = []
        self._quarantined_sessions: set[str] = set()

    @property
    def blocked_count(self) -> int:
        return self._blocked_count

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "status": "ACTIVE_SENTINEL",
            "evaluations_total": len(self._threat_history),
            "blocked_threats": self._blocked_count,
            "quarantined_sessions": len(self._quarantined_sessions),
        }

    def evaluate_prompt(self, prompt: str, session_id: str = "") -> BlueTeamEvaluation:
        """Inspect a user prompt for injection, exfiltration, or adversarial attacks."""
        if not prompt or not isinstance(prompt, str):
            return BlueTeamEvaluation(allowed=True, threat_level=ThreatLevel.NONE, threat_score=0.0)

        if session_id in self._quarantined_sessions:
            return BlueTeamEvaluation(
                allowed=False,
                threat_level=ThreatLevel.CRITICAL,
                threat_score=1.0,
                reasons=[f"Session '{session_id}' is currently quarantined due to a critical security incident."],
                threat_vector="quarantined_session",
                is_emergency=True,
            )

        reasons = []
        threat_score = 0.0
        threat_vector = "benign"

        # Check prompt injection patterns
        for pattern, desc in self.INJECTION_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                reasons.append(f"Prompt Attack: {desc}")
                threat_score = max(threat_score, 0.75)
                threat_vector = "prompt_injection"

        # Check dangerous system commands embedded in prompt
        for pattern, desc in self.DANGEROUS_COMMAND_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                reasons.append(f"Dangerous Command Intent: {desc}")
                threat_score = max(threat_score, 0.90)
                threat_vector = "critical_command_injection"

        # Check SSRF and exploit vectors
        for pattern, desc in self.CODE_EXPLOIT_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                reasons.append(f"Exploit Vector: {desc}")
                threat_score = max(threat_score, 0.85)
                threat_vector = "exploit_signature"

        return self._build_verdict(reasons, threat_score, threat_vector, {"prompt_snippet": prompt[:150]})

    def evaluate_command(self, command: str) -> BlueTeamEvaluation:
        """Inspect shell/OS command before execution."""
        if not command or not isinstance(command, str):
            return BlueTeamEvaluation(allowed=True, threat_level=ThreatLevel.NONE, threat_score=0.0)

        reasons = []
        threat_score = 0.0
        threat_vector = "benign"

        for pattern, desc in self.DANGEROUS_COMMAND_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                reasons.append(f"Lethal Command Blocked: {desc}")
                threat_score = max(threat_score, 0.95)
                threat_vector = "lethal_os_command"

        # Check for path traversal in command
        for pattern, desc in self.CODE_EXPLOIT_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                reasons.append(f"SSRF / Traversal in Command: {desc}")
                threat_score = max(threat_score, 0.88)
                threat_vector = "ssrf_or_traversal"

        return self._build_verdict(reasons, threat_score, threat_vector, {"command": command[:200]})

    def evaluate_code(self, code: str) -> BlueTeamEvaluation:
        """Static AST and signature security analysis on generated code."""
        if not code or not isinstance(code, str):
            return BlueTeamEvaluation(allowed=True, threat_level=ThreatLevel.NONE, threat_score=0.0)

        reasons = []
        threat_score = 0.0
        threat_vector = "benign"

        # Secret leaks in code
        for pattern, desc in self.SECRET_PATTERNS:
            if re.search(pattern, code):
                reasons.append(f"Hardcoded Secret / Credential Leak: {desc}")
                threat_score = max(threat_score, 0.80)
                threat_vector = "secret_leak"

        # AST-level inspection
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Check for direct dangerous socket connections
                if isinstance(node, ast.Call):
                    func_id = ""
                    if isinstance(node.func, ast.Name):
                        func_id = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_id = node.func.attr
                    
                    if func_id in ("eval", "exec") and len(node.args) > 0:
                        # Dynamic execution
                        reasons.append("Dynamic Code Execution (eval/exec)")
                        threat_score = max(threat_score, 0.65)
                        threat_vector = "dynamic_execution"
        except SyntaxError:
            pass  # Non-python code or partial snippet, rely on regex

        return self._build_verdict(reasons, threat_score, threat_vector, {"code_snippet": code[:150]})

    def quarantine_session(self, session_id: str):
        """Place a session under quarantine."""
        if session_id:
            self._quarantined_sessions.add(session_id)

    def lift_quarantine(self, session_id: str):
        """Lift quarantine from a session."""
        self._quarantined_sessions.discard(session_id)

    def _build_verdict(
        self,
        reasons: list[str],
        threat_score: float,
        threat_vector: str,
        details: dict[str, Any],
    ) -> BlueTeamEvaluation:
        """Build evaluation result and map score to level."""
        if not reasons:
            level = ThreatLevel.NONE
            allowed = True
            is_emergency = False
        elif threat_score >= 0.85:
            level = ThreatLevel.CRITICAL
            allowed = False
            is_emergency = True
            self._blocked_count += 1
        elif threat_score >= 0.65:
            level = ThreatLevel.HIGH
            allowed = False
            is_emergency = False
            self._blocked_count += 1
        elif threat_score >= 0.40:
            level = ThreatLevel.MEDIUM
            allowed = True
            is_emergency = False
        else:
            level = ThreatLevel.LOW
            allowed = True
            is_emergency = False

        eval_res = BlueTeamEvaluation(
            allowed=allowed,
            threat_level=level,
            threat_score=threat_score,
            reasons=reasons,
            threat_vector=threat_vector,
            is_emergency=is_emergency,
            details=details,
        )
        self._threat_history.append(eval_res)
        if len(self._threat_history) > 500:
            self._threat_history = self._threat_history[-500:]
        return eval_res
