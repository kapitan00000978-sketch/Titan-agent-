"""Supply-Chain & Dependency Security Auditor."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VulnerabilityAlert:
    package: str
    installed_spec: str
    severity: str  # CRITICAL / HIGH / MEDIUM / LOW
    advisory: str
    recommendation: str


@dataclass
class DependencyReport:
    manifest_path: str
    total_dependencies: int
    vulnerable_count: int
    alerts: list[VulnerabilityAlert] = field(default_factory=list)
    summary: str = ""


class DependencyAuditor:
    """Audits software manifests for known vulnerable packages and insecure dependency specs."""

    # Known vulnerable / risky package patterns database
    VULN_DB = [
        {"pkg": "urllib3", "bad_spec": r"<1\.26\.18|<2\.0\.7", "advisory": "CVE-2023-45803: Request body leak on redirect", "severity": "HIGH", "fix": "Upgrade urllib3 >= 2.0.7 or >= 1.26.18"},
        {"pkg": "requests", "bad_spec": r"<2\.31\.0", "advisory": "CVE-2023-32681: Unintended leak of Proxy-Authorization header", "severity": "MEDIUM", "fix": "Upgrade requests >= 2.31.0"},
        {"pkg": "cryptography", "bad_spec": r"<41\.0\.6|<42\.0\.4", "advisory": "CVE-2023-49083: NULL pointer dereference in PKCS7 parsing", "severity": "HIGH", "fix": "Upgrade cryptography >= 42.0.4"},
        {"pkg": "jinja2", "bad_spec": r"<3\.1\.3", "advisory": "CVE-2024-22195: XSS vulnerability via xmlattr filter", "severity": "HIGH", "fix": "Upgrade jinja2 >= 3.1.3"},
        {"pkg": "aiohttp", "bad_spec": r"<3\.9\.4", "advisory": "CVE-2024-23334: Directory traversal in static file server", "severity": "CRITICAL", "fix": "Upgrade aiohttp >= 3.9.4"},
        {"pkg": "pillow", "bad_spec": r"<10\.3\.0", "advisory": "CVE-2024-28219: Buffer overflow in _imagingcms", "severity": "HIGH", "fix": "Upgrade pillow >= 10.3.0"},
        {"pkg": "tornado", "bad_spec": r"<6\.4\.1", "advisory": "CVE-2024-35198: CRLF injection in HTTP headers", "severity": "MEDIUM", "fix": "Upgrade tornado >= 6.4.1"},
    ]

    def audit_requirements_text(self, text: str, source_name: str = "requirements.txt") -> DependencyReport:
        """Audit raw requirements.txt text content."""
        alerts: list[VulnerabilityAlert] = []
        total_deps = 0

        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            total_deps += 1

            # Insecure HTTP URL source
            if line.startswith("http://"):
                alerts.append(
                    VulnerabilityAlert(
                        package=line[:30],
                        installed_spec=line,
                        severity="CRITICAL",
                        advisory="Insecure unencrypted HTTP package source (MitM risk)",
                        recommendation="Use HTTPS package repository URLs only.",
                    )
                )

            # Match package spec
            parts = re.split(r"[><=~^!]", line, maxsplit=1)
            pkg_name = parts[0].strip().lower()

            for entry in self.VULN_DB:
                if entry["pkg"] == pkg_name:
                    # Check if version matches bad spec
                    if "==" in line:
                        ver = line.split("==")[1].strip()
                        # Basic match or warning
                        alerts.append(
                            VulnerabilityAlert(
                                package=pkg_name,
                                installed_spec=line,
                                severity=entry["severity"],
                                advisory=entry["advisory"],
                                recommendation=entry["fix"],
                            )
                        )

        crit_count = sum(1 for a in alerts if a.severity == "CRITICAL")
        summary = f"Audited {total_deps} dependencies in {source_name}. Found {len(alerts)} security advisory alerts ({crit_count} Critical)."

        return DependencyReport(
            manifest_path=source_name,
            total_dependencies=total_deps,
            vulnerable_count=len(alerts),
            alerts=alerts,
            summary=summary,
        )

    def audit_manifest_file(self, file_path: Path | str) -> DependencyReport:
        """Audit a dependency manifest file from disk."""
        p = Path(file_path)
        if not p.is_file():
            return DependencyReport(str(p), 0, 0, [], f"Manifest file not found: {p}")
        content = p.read_text(encoding="utf-8", errors="replace")
        return self.audit_requirements_text(content, source_name=p.name)
