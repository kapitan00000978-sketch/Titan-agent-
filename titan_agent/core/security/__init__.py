"""Dual-Shield Cyber Defense Subsystem for Universal Agent HP.

Provides:
- BlueTeamSentinel: Always-on continuous security monitoring and defense.
- EmergencyRedTeam: Autonomous counter-strike, payload deconstruction, and containment.
- DualShieldOrchestrator: Unified manager coordinating defensive checks and emergency responses.
- SASTScanner: Static application security testing & OWASP Top 10 analysis.
- DependencyAuditor: Supply-chain manifest vulnerability auditing.
- SecretScanner: Shannon-entropy secret detection and auto-redaction.
- ThreatModelEngine: MITRE ATT&CK taxonomy modeling and forensic incident reporting.
- IPDefenseManager: Defensive IP inspection, geo-logging, and automated banning.
"""

from .blue_team import BlueTeamEvaluation, BlueTeamSentinel, ThreatLevel
from .dependency_auditor import DependencyAuditor, DependencyReport, VulnerabilityAlert
from .dual_shield import DualShieldOrchestrator, SecurityIncident
from .ip_defense import BannedIPEntry, IPDefenseManager, IPGeoInfo
from .red_team import EmergencyRedTeam, RedTeamResponse
from .sast import SASTFinding, SASTReport, SASTScanner
from .secret_scanner import SecretFinding, SecretScanner
from .threat_model import ThreatModelEngine, ThreatVectorProfile

__all__ = [
    "BlueTeamSentinel",
    "BlueTeamEvaluation",
    "ThreatLevel",
    "EmergencyRedTeam",
    "RedTeamResponse",
    "DualShieldOrchestrator",
    "SecurityIncident",
    "SASTScanner",
    "SASTReport",
    "SASTFinding",
    "DependencyAuditor",
    "DependencyReport",
    "VulnerabilityAlert",
    "SecretScanner",
    "SecretFinding",
    "ThreatModelEngine",
    "ThreatVectorProfile",
    "IPDefenseManager",
    "BannedIPEntry",
    "IPGeoInfo",
]
