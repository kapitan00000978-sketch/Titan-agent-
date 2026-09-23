"""Dual-Shield Cyber Defense Subsystem for Universal Agent HP.

Provides:
- BlueTeamSentinel: Always-on continuous security monitoring and defense.
- EmergencyRedTeam: Autonomous counter-strike, payload deconstruction, and containment.
- DualShieldOrchestrator: Unified manager coordinating defensive checks and emergency responses.
"""

from .blue_team import BlueTeamEvaluation, BlueTeamSentinel, ThreatLevel
from .dual_shield import DualShieldOrchestrator, SecurityIncident
from .red_team import EmergencyRedTeam, RedTeamResponse

__all__ = [
    "BlueTeamSentinel",
    "BlueTeamEvaluation",
    "ThreatLevel",
    "EmergencyRedTeam",
    "RedTeamResponse",
    "DualShieldOrchestrator",
    "SecurityIncident",
]
