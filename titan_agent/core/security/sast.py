"""SAST (Static Application Security Testing) & OWASP Top 10 Security Engine."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SASTFinding:
    rule_id: str
    category: str  # OWASP category
    title: str
    severity: str  # CRITICAL / HIGH / MEDIUM / LOW
    line: int
    snippet: str
    remediation: str


@dataclass
class SASTReport:
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    findings: list[SASTFinding] = field(default_factory=list)
    summary: str = ""


class SASTScanner:
    """Static Application Security Testing Engine for multi-language codebases."""

    OWASP_RULES = [
        # Injection
        {
            "id": "SEC-INJ-001",
            "category": "A03:2021-Injection (SQL)",
            "pattern": r"(execute|cursor\.execute)\s*\(\s*f?['\"].*(SELECT|INSERT|UPDATE|DELETE).*%s.*['\"]",
            "title": "SQL String Formatting / Potential SQL Injection",
            "severity": "HIGH",
            "remediation": "Use parameterized queries with placeholders instead of string formatting.",
        },
        {
            "id": "SEC-INJ-002",
            "category": "A03:2021-Injection (Command)",
            "pattern": r"(subprocess\.(Popen|run|call|check_output)|os\.system)\s*\(.*shell\s*=\s*True",
            "title": "Subprocess Shell=True Command Injection Risk",
            "severity": "HIGH",
            "remediation": "Set shell=False and pass command as a list of arguments, or sanitize with shlex.quote().",
        },
        {
            "id": "SEC-DESER-001",
            "category": "A08:2021-Software and Data Integrity Failures",
            "pattern": r"(pickle\.loads?|_pickle\.loads?|yaml\.load\s*\(.*Loader\s*=\s*yaml\.Loader\))",
            "title": "Insecure Deserialization (pickle/unsafe YAML)",
            "severity": "CRITICAL",
            "remediation": "Use safe deserialization formats like json or yaml.safe_load().",
        },
        # Misconfiguration
        {
            "id": "SEC-CONF-001",
            "category": "A05:2021-Security Misconfiguration",
            "pattern": r"(verify\s*=\s*False|check_hostname\s*=\s*False)",
            "title": "Disabled SSL/TLS Certificate Verification",
            "severity": "HIGH",
            "remediation": "Enable SSL verification (verify=True) to prevent Man-in-the-Middle (MitM) attacks.",
        },
        # SSRF
        {
            "id": "SEC-SSRF-001",
            "category": "A10:2021-Server-Side Request Forgery",
            "pattern": r"(requests\.(get|post|put|delete)|urllib\.request\.urlopen|aiohttp\..*)\s*\(\s*.*(169\.254\.169\.254|localhost|127\.0\.0\.1)",
            "title": "Potential SSRF to Internal Network / Metadata Service",
            "severity": "HIGH",
            "remediation": "Validate and whitelist destination hostnames; block internal IP ranges (127.0.0.0/8, 169.254.0.0/16, 10.0.0.0/8).",
        },
        # Path Traversal
        {
            "id": "SEC-TRAV-001",
            "category": "A01:2021-Broken Access Control",
            "pattern": r"(open|Path|read_text|write_text)\s*\(.*(\.\./|\.\.\\)",
            "title": "Direct Path Traversal Sequence in File Operation",
            "severity": "HIGH",
            "remediation": "Resolve paths against an allowed base directory and verify target.is_relative_to(base).",
        },
    ]

    def scan_code(self, code: str, filename: str = "code.py") -> SASTReport:
        """Analyze source code string for vulnerabilities."""
        findings: list[SASTFinding] = []
        if not code:
            return SASTReport(0, 0, 0, 0, 0, [], "Empty code snippet.")

        lines = code.splitlines()

        # 1. Regex Rule Scanner
        for idx, line in enumerate(lines, 1):
            for rule in self.OWASP_RULES:
                if re.search(rule["pattern"], line, re.IGNORECASE):
                    findings.append(
                        SASTFinding(
                            rule_id=rule["id"],
                            category=rule["category"],
                            title=rule["title"],
                            severity=rule["severity"],
                            line=idx,
                            snippet=line.strip(),
                            remediation=rule["remediation"],
                        )
                    )

        # 2. Python AST Dynamic Calls Scanner
        if filename.endswith((".py", ".pyw")):
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        func_name = ""
                        if isinstance(node.func, ast.Name):
                            func_name = node.func.id
                        elif isinstance(node.func, ast.Attribute):
                            func_name = node.func.attr

                        if func_name in ("eval", "exec"):
                            lineno = getattr(node, "lineno", 1)
                            snippet = lines[lineno - 1].strip() if lineno <= len(lines) else f"{func_name}(...)"
                            findings.append(
                                SASTFinding(
                                    rule_id="SEC-DYN-001",
                                    category="A03:2021-Injection",
                                    title=f"Arbitrary Code Execution ({func_name})",
                                    severity="CRITICAL",
                                    line=lineno,
                                    snippet=snippet,
                                    remediation=f"Avoid dynamic {func_name}(). Use ast.literal_eval() for data or safe dispatch maps.",
                                )
                            )
            except SyntaxError:
                pass  # Non-python or snippet, regex already scanned

        crit = sum(1 for f in findings if f.severity == "CRITICAL")
        high = sum(1 for f in findings if f.severity == "HIGH")
        med = sum(1 for f in findings if f.severity == "MEDIUM")
        low = sum(1 for f in findings if f.severity == "LOW")

        summary = f"SAST Scan found {len(findings)} issues ({crit} Critical, {high} High, {med} Medium, {low} Low)."

        return SASTReport(
            total_findings=len(findings),
            critical_count=crit,
            high_count=high,
            medium_count=med,
            low_count=low,
            findings=findings,
            summary=summary,
        )
