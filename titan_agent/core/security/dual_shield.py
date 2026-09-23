"""Dual-Shield Orchestrator: Bridges continuous Blue Team monitoring with emergency Red Team response."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .blue_team import BlueTeamEvaluation, BlueTeamSentinel, ThreatLevel
from .red_team import EmergencyRedTeam, RedTeamResponse


@dataclass
class SecurityIncident:
    """Recorded security incident."""
    id: str
    timestamp: float
    threat_level: str
    vector: str
    reasons: list[str]
    red_team_response: RedTeamResponse | None = None


class DualShieldOrchestrator:
    """Enterprise Cyber Defense Orchestrator for Universal Agent HP.

    - Blue Team: Always Active, Continuous In-Line & Pre-Execution Verification.
    - Red Team: Emergency-Only Trigger, Autonomous Containment & Forensics.
    """

    _instance: DualShieldOrchestrator | None = None

    def __init__(self):
        self.blue_team = BlueTeamSentinel()
        self.red_team = EmergencyRedTeam()
        self.incidents: list[SecurityIncident] = []

    @classmethod
    def get_instance(cls) -> DualShieldOrchestrator:
        if cls._instance is None:
            cls._instance = DualShieldOrchestrator()
        return cls._instance

    async def evaluate_prompt(
        self,
        prompt: str,
        session_id: str = "",
        llm_client: Any = None,
    ) -> tuple[bool, str, RedTeamResponse | None]:
        """Evaluate incoming user prompt through Blue Team, trigger Red Team if critical."""
        eval_res = self.blue_team.evaluate_prompt(prompt, session_id=session_id)
        
        if eval_res.allowed:
            return True, "Allowed by Blue Team sentinel.", None

        red_response = None
        if eval_res.is_emergency or eval_res.threat_level == ThreatLevel.CRITICAL:
            # Trigger Emergency Red Team
            self.blue_team.quarantine_session(session_id)
            red_response = await self.red_team.counter_strike(
                threat_vector=eval_res.threat_vector,
                payload_snippet=prompt,
                reasons=eval_res.reasons,
                session_id=session_id,
                llm_client=llm_client,
            )
            incident = SecurityIncident(
                id=red_response.incident_id,
                timestamp=time.time(),
                threat_level="CRITICAL",
                vector=eval_res.threat_vector,
                reasons=eval_res.reasons,
                red_team_response=red_response,
            )
            self.incidents.append(incident)
            block_msg = f"🚨 SECURITY BLOCK ({eval_res.threat_level.value.upper()}): {'; '.join(eval_res.reasons)}\nEmergency Red Team activated: {red_response.incident_id}"
            return False, block_msg, red_response

        # High/Medium block without emergency red team
        block_msg = f"🛡️ BLUE TEAM BLOCKED: {'; '.join(eval_res.reasons)}"
        return False, block_msg, None

    async def evaluate_command(
        self,
        command: str,
        session_id: str = "",
        llm_client: Any = None,
    ) -> tuple[bool, str, RedTeamResponse | None]:
        """Evaluate shell command before execution."""
        eval_res = self.blue_team.evaluate_command(command)
        
        if eval_res.allowed:
            return True, "Allowed by Blue Team sentinel.", None

        red_response = None
        if eval_res.is_emergency or eval_res.threat_level == ThreatLevel.CRITICAL:
            self.blue_team.quarantine_session(session_id)
            red_response = await self.red_team.counter_strike(
                threat_vector=eval_res.threat_vector,
                payload_snippet=command,
                reasons=eval_res.reasons,
                session_id=session_id,
                llm_client=llm_client,
            )
            incident = SecurityIncident(
                id=red_response.incident_id,
                timestamp=time.time(),
                threat_level="CRITICAL",
                vector=eval_res.threat_vector,
                reasons=eval_res.reasons,
                red_team_response=red_response,
            )
            self.incidents.append(incident)
            block_msg = f"🚨 LETHAL COMMAND BLOCKED: {'; '.join(eval_res.reasons)}\nEmergency Red Team Counter-Strike: {red_response.incident_id}"
            return False, block_msg, red_response

        return False, f"🛡️ BLUE TEAM BLOCKED: {'; '.join(eval_res.reasons)}", None

    def get_security_status(self) -> dict[str, Any]:
        """Get real-time Dual-Shield status and telemetry."""
        return {
            "shield_status": "ONLINE",
            "blue_team": {
                "state": "ALWAYS_ON_MONITORING",
                "blocked_threats": self.blue_team.blocked_count,
                "stats": self.blue_team.stats,
            },
            "red_team": {
                "state": "STANDBY_EMERGENCY_ONLY" if not self.red_team.total_incidents else f"ACTIVE_INCIDENTS_{self.red_team.total_incidents}",
                "total_counter_strikes": self.red_team.total_incidents,
                "recent_incidents": [
                    {"id": inc.incident_id, "vector": inc.threat_vector, "time": inc.triggered_at}
                    for inc in self.red_team.incident_history[-5:]
                ],
            },
            "total_recorded_incidents": len(self.incidents),
        }
