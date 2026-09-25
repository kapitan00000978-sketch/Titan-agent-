"""
Domain Manager for Universal Agent HP.
Coordinates active industry domain profiles, custom profile persistence, and system prompt steering.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from .builtin_domains import BUILTIN_DOMAINS
from .profile import DomainProfile

log = logging.getLogger(__name__)

DEFAULT_DOMAINS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".titan" / "domains"


class DomainManager:
    """Manages active and registered domain profiles for Universal Agent HP."""

    _instance: DomainManager | None = None

    def __init__(self, domains_dir: Path | None = None, default_domain: str | None = None):
        self.domains_dir = Path(domains_dir) if domains_dir else DEFAULT_DOMAINS_DIR
        self.domains_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: dict[str, DomainProfile] = dict(BUILTIN_DOMAINS)
        self.load_custom_domains()

        # Determine initial active domain
        configured = (
            default_domain
            or os.getenv("TITAN_DOMAIN", "")
            or "universal"
        ).strip().lower()

        if configured in self._profiles:
            self.active_domain_name = configured
        else:
            self.active_domain_name = "universal"

    @classmethod
    def get_instance(cls) -> DomainManager:
        """Global singleton accessor."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_custom_domains(self) -> None:
        """Loads custom user-defined domain profiles from disk."""
        if not self.domains_dir.exists():
            return
        for fpath in self.domains_dir.glob("*.json"):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                profile = DomainProfile.from_dict(data)
                profile.is_builtin = False
                self._profiles[profile.name] = profile
                log.info("Loaded custom domain profile: %s from %s", profile.name, fpath)
            except Exception as e:  # noqa: BLE001
                log.warning("Failed to load custom domain from %s: %s", fpath, e)

    @property
    def active_domain(self) -> DomainProfile:
        """Returns the currently active DomainProfile."""
        return self._profiles.get(self.active_domain_name, self._profiles["universal"])

    def switch_domain(self, domain_name: str) -> DomainProfile:
        """Switches the active domain profile. Raises ValueError if domain is unknown."""
        key = str(domain_name).strip().lower()
        # Support aliases
        aliases = {
            "dev": "software_engineering",
            "coding": "software_engineering",
            "code": "software_engineering",
            "fin": "finance",
            "money": "finance",
            "med": "healthcare",
            "health": "healthcare",
            "law": "legal",
            "mark": "marketing",
            "sci": "science",
            "edu": "education",
            "shop": "ecommerce",
            "store": "ecommerce",
            "help": "customer_support",
            "support": "customer_support",
            "video": "multimedia",
            "blender": "multimedia",
            "sec": "cybersecurity",
            "security": "cybersecurity",
            "all": "universal",
            "general": "universal",
        }
        key = aliases.get(key, key)

        if key not in self._profiles:
            available = ", ".join(sorted(self._profiles.keys()))
            raise ValueError(f"Unknown domain '{domain_name}'. Available domains: {available}")

        self.active_domain_name = key
        log.info("Switched active domain to: %s (%s)", key, self.active_domain.display_name)
        return self.active_domain

    def register_domain(
        self,
        profile: DomainProfile,
        persist: bool = True,
    ) -> DomainProfile:
        """Registers a new or updated domain profile, optionally persisting it to disk."""
        key = profile.name.strip().lower()
        profile.name = key
        self._profiles[key] = profile

        if persist:
            fpath = self.domains_dir / f"{key}.json"
            fpath.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
            log.info("Persisted custom domain profile '%s' to %s", key, fpath)

        return profile

    def delete_custom_domain(self, domain_name: str) -> bool:
        """Deletes a custom domain. Built-in domains cannot be deleted."""
        key = str(domain_name).strip().lower()
        if key not in self._profiles:
            return False
        if self._profiles[key].is_builtin:
            raise ValueError(f"Cannot delete built-in system domain '{key}'.")

        del self._profiles[key]
        fpath = self.domains_dir / f"{key}.json"
        if fpath.exists():
            fpath.unlink()

        if self.active_domain_name == key:
            self.active_domain_name = "universal"
        return True

    def list_domains(self) -> list[dict[str, Any]]:
        """Returns a list of summary dicts for all available domains."""
        results = []
        for name in sorted(self._profiles.keys()):
            p = self._profiles[name]
            results.append({
                "name": p.name,
                "display_name": p.display_name,
                "icon": p.icon,
                "description": p.description,
                "is_active": (p.name == self.active_domain_name),
                "is_builtin": p.is_builtin,
                "guardrails_count": len(p.mandatory_guardrails),
                "preferred_tools_count": len(p.preferred_tools),
            })
        return results

    def get_domain(self, name: str) -> DomainProfile | None:
        """Retrieves a DomainProfile by name."""
        return self._profiles.get(str(name).strip().lower())

    def build_system_overlay(self) -> str:
        """Builds the active domain overlay text for system prompt injection."""
        return self.active_domain.build_overlay_text()

    def is_tool_allowed(self, tool_name: str) -> tuple[bool, str | None]:
        """Checks if a tool is allowed under the active domain profile."""
        current = self.active_domain
        if tool_name in current.forbidden_tools:
            return False, f"Tool '{tool_name}' is restricted under active domain '{current.name}'."
        return True, None
