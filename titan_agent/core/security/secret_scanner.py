"""Secret & High-Entropy Credential Scanner with Automatic Redaction."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class SecretFinding:
    secret_type: str
    match: str
    entropy: float
    start: int
    end: int
    severity: str  # CRITICAL / HIGH / MEDIUM


class SecretScanner:
    """Detects API keys, tokens, private keys, and high-entropy secrets."""

    PATTERNS = [
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key", "CRITICAL"),
        (r"ghp_[0-9a-zA-Z]{36}", "GitHub Personal Access Token", "CRITICAL"),
        (r"github_pat_[0-9a-zA-Z_]{82}", "GitHub Fine-Grained PAT", "CRITICAL"),
        (r"sk-[a-zA-Z0-9_-]{32,}", "OpenAI/Anthropic API Key", "CRITICAL"),
        (r"xox[baprs]-[0-9a-zA-Z]{10,48}", "Slack Token", "CRITICAL"),
        (r"AIza[0-9A-Za-z-_]{35}", "Google API Key", "HIGH"),
        (r"-----BEGIN (RSA|EC|OPENSSH|PGP|PRIVATE) KEY-----", "Private Key / Certificate", "CRITICAL"),
        (r"(password|passwd|secret|api_key|token)\s*[:=]\s*['\"][^\s'\"]{8,}['\"]", "Hardcoded Secret Literal", "HIGH"),
    ]

    @staticmethod
    def shannon_entropy(data: str) -> float:
        """Calculate the Shannon entropy of a string."""
        if not data:
            return 0.0
        entropy = 0.0
        length = len(data)
        freq: dict[str, int] = {}
        for char in data:
            freq[char] = freq.get(char, 0) + 1
        for count in freq.values():
            p = count / length
            entropy -= p * math.log2(p)
        return entropy

    def scan(self, text: str) -> list[SecretFinding]:
        """Scan text and return all detected secret findings."""
        if not text:
            return []
        findings: list[SecretFinding] = []

        # 1. Regex Pattern Matching
        for pattern, desc, severity in self.PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                val = match.group(0)
                entropy = self.shannon_entropy(val)
                findings.append(
                    SecretFinding(
                        secret_type=desc,
                        match=val,
                        entropy=round(entropy, 2),
                        start=match.start(),
                        end=match.end(),
                        severity=severity,
                    )
                )

        # 2. High Entropy Word Detection (e.g. hex/base64 blobs > 24 chars with entropy > 4.2)
        words = re.findall(r"[A-Za-z0-9+/=_-]{24,}", text)
        for w in words:
            # Skip if already captured by regex patterns
            if any(w in f.match for f in findings):
                continue
            entropy = self.shannon_entropy(w)
            if entropy > 4.3 and not w.isdigit():
                findings.append(
                    SecretFinding(
                        secret_type="High-Entropy Secret / Token Blob",
                        match=w,
                        entropy=round(entropy, 2),
                        start=text.find(w),
                        end=text.find(w) + len(w),
                        severity="MEDIUM",
                    )
                )

        return findings

    def redact(self, text: str) -> str:
        """Redact all detected secrets from text to prevent log leaks."""
        if not text:
            return ""
        findings = self.scan(text)
        if not findings:
            return text

        redacted = text
        # Sort by match length descending to prevent partial replacement bugs
        for f in sorted(findings, key=lambda x: len(x.match), reverse=True):
            if f.secret_type == "Private Key / Certificate":
                mask = "[REDACTED_PRIVATE_KEY]"
            else:
                visible = f.match[:4] if len(f.match) > 8 else "***"
                mask = f"{visible}...[REDACTED_{f.secret_type.upper().replace(' ', '_')}]"
            redacted = redacted.replace(f.match, mask)
        return redacted
