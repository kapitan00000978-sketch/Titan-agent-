"""
Titan Agent Core - next-gen agent architecture.

Phase 2 modules:
- reasoning:      ReAct + Plan-and-Execute reasoning engines
- memory:         Episodic/Semantic/Procedural/Working memory with consolidation
- reflection:     Self-correction and lessons learned
- orchestration:  Multi-agent teams (sequential/parallel/consensus/supervisor)
- guardrails:     Policy engine + human-in-the-loop approval gates
- tools:          Discovery, composition, sandboxing, policy-guarded execution
"""
from . import (
    guardrails,
    memory,
    orchestration,
    reasoning,
    reflection,
    tools,
)

__all__ = [
    "guardrails",
    "memory",
    "orchestration",
    "reasoning",
    "reflection",
    "tools",
]