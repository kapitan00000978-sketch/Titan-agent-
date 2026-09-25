"""
Domain Profile definition for Universal Agent HP.
Enables tailoring the agent for any industry, field, or enterprise domain.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DomainProfile:
    """Configurable domain profile defining persona, guardrails, tools, and instructions."""

    name: str
    display_name: str
    icon: str
    description: str
    system_prompt_overlay: str
    mandatory_guardrails: list[str] = field(default_factory=list)
    preferred_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    suggested_skills: list[str] = field(default_factory=list)
    custom_rules: dict[str, Any] = field(default_factory=dict)
    is_builtin: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize domain profile to a dictionary."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "icon": self.icon,
            "description": self.description,
            "system_prompt_overlay": self.system_prompt_overlay,
            "mandatory_guardrails": self.mandatory_guardrails,
            "preferred_tools": self.preferred_tools,
            "forbidden_tools": self.forbidden_tools,
            "suggested_skills": self.suggested_skills,
            "custom_rules": self.custom_rules,
            "is_builtin": self.is_builtin,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainProfile:
        """Instantiate a DomainProfile from a dictionary."""
        return cls(
            name=str(data["name"]).strip().lower(),
            display_name=str(data.get("display_name", data["name"])),
            icon=str(data.get("icon", "🌐")),
            description=str(data.get("description", "")),
            system_prompt_overlay=str(data.get("system_prompt_overlay", "")),
            mandatory_guardrails=list(data.get("mandatory_guardrails", [])),
            preferred_tools=list(data.get("preferred_tools", [])),
            forbidden_tools=list(data.get("forbidden_tools", [])),
            suggested_skills=list(data.get("suggested_skills", [])),
            custom_rules=dict(data.get("custom_rules", {})),
            is_builtin=bool(data.get("is_builtin", False)),
        )

    def build_overlay_text(self) -> str:
        """Renders the domain overlay to inject into the system prompt."""
        lines = [
            f"### ACTIVE INDUSTRY DOMAIN: {self.icon} {self.display_name.upper()} ({self.name})",
            self.description.strip(),
            "",
            "#### DOMAIN OPERATIONAL INSTRUCTIONS & STANDARDS:",
            self.system_prompt_overlay.strip(),
        ]

        if self.mandatory_guardrails:
            lines.append("")
            lines.append("#### MANDATORY DOMAIN GUARDRAILS & COMPLIANCE RULES:")
            for g in self.mandatory_guardrails:
                lines.append(f"- ⚠️ {g}")

        if self.preferred_tools:
            lines.append("")
            lines.append(f"#### RECOMMENDED DOMAIN TOOLS: {', '.join(self.preferred_tools)}")

        return "\n".join(lines)
