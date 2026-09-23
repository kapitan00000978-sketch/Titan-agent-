"""Defensive IP Banning, Geo-Logging & Connection Threat Intelligence."""

from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BannedIPEntry:
    ip: str
    banned_at: float
    duration_seconds: float  # 0 for permanent
    reason: str
    incident_id: str = ""
    country: str = "Unknown"
    city: str = "Unknown"
    isp: str = "Unknown"

    @property
    def is_expired(self) -> bool:
        if self.duration_seconds <= 0:
            return False
        return (time.time() - self.banned_at) > self.duration_seconds


@dataclass
class IPGeoInfo:
    ip: str
    is_private: bool
    country: str = "Private/Local Network"
    city: str = "Local"
    isp: str = "Localhost/LAN"


class IPDefenseManager:
    """Defensive IP Inspection, Automated Banning, and Geo-Logging."""

    def __init__(self, default_ban_duration: float = 86400.0):
        self._default_ban_duration = default_ban_duration
        self._banned_ips: dict[str, BannedIPEntry] = {}
        self._ip_violation_counts: dict[str, int] = {}
        self._whitelist: set[str] = {"127.0.0.1", "::1", "localhost"}

    def inspect_ip(self, ip_str: str) -> IPGeoInfo:
        """Inspect an IP address and resolve location metadata."""
        ip_clean = (ip_str or "").strip()
        try:
            ip_obj = ipaddress.ip_address(ip_clean)
            is_priv = ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local
            if is_priv:
                return IPGeoInfo(ip=ip_clean, is_private=True, country="Private/LAN", city="Local", isp="Private Subnet")
            return IPGeoInfo(
                ip=ip_clean,
                is_private=False,
                country="External Internet",
                city="Remote Gateway",
                isp="Autonomous System / ISP",
            )
        except ValueError:
            return IPGeoInfo(ip=ip_clean, is_private=True, country="Unknown", city="Unknown", isp="Invalid IP")

    def ban_ip(
        self,
        ip_str: str,
        reason: str,
        duration: float | None = None,
        incident_id: str = "",
        country: str = "Unknown",
        city: str = "Unknown",
        isp: str = "Unknown",
    ) -> BannedIPEntry | None:
        """Ban an IP address defensively."""
        ip_clean = (ip_str or "").strip()
        if not ip_clean or ip_clean in self._whitelist:
            return None

        dur = self._default_ban_duration if duration is None else float(duration)
        geo = self.inspect_ip(ip_clean)
        entry = BannedIPEntry(
            ip=ip_clean,
            banned_at=time.time(),
            duration_seconds=dur,
            reason=reason,
            incident_id=incident_id,
            country=country if country != "Unknown" else geo.country,
            city=city if city != "Unknown" else geo.city,
            isp=isp if isp != "Unknown" else geo.isp,
        )
        self._banned_ips[ip_clean] = entry
        return entry

    def unban_ip(self, ip_str: str) -> bool:
        """Unban an IP address."""
        ip_clean = (ip_str or "").strip()
        return bool(self._banned_ips.pop(ip_clean, None))

    def is_banned(self, ip_str: str) -> bool:
        """Check if an IP address is currently banned."""
        ip_clean = (ip_str or "").strip()
        if not ip_clean or ip_clean in self._whitelist:
            return False

        entry = self._banned_ips.get(ip_clean)
        if not entry:
            return False

        if entry.is_expired:
            self._banned_ips.pop(ip_clean, None)
            return False

        return True

    def record_violation(self, ip_str: str, max_violations: int = 3, reason: str = "Repeated security violations") -> bool:
        """Record a threat violation; auto-bans if max_violations threshold is reached."""
        ip_clean = (ip_str or "").strip()
        if not ip_clean or ip_clean in self._whitelist:
            return False

        cnt = self._ip_violation_counts.get(ip_clean, 0) + 1
        self._ip_violation_counts[ip_clean] = cnt
        if cnt >= max_violations:
            self.ban_ip(ip_clean, reason=f"{reason} ({cnt} infractions)")
            return True
        return False

    def list_banned(self) -> list[BannedIPEntry]:
        """List all active banned IP entries."""
        now = time.time()
        active = []
        for ip, entry in list(self._banned_ips.items()):
            if entry.is_expired:
                self._banned_ips.pop(ip, None)
            else:
                active.append(entry)
        return active
