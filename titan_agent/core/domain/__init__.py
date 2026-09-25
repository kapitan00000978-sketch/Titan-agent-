"""
Universal Agent HP — Omni-Domain Adaptation Package.
Allows configuring and tailoring the agent for all industries and fields.
"""
from __future__ import annotations

from .builtin_domains import BUILTIN_DOMAINS
from .manager import DomainManager
from .profile import DomainProfile

__all__ = [
    "BUILTIN_DOMAINS",
    "DomainManager",
    "DomainProfile",
]
