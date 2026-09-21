"""
Orchestration Types - multi-agent roles, messages, specs and results.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class AgentRole(str, Enum):
    """Predefined agent roles in the team."""

    SUPERVISOR = "supervisor"    # Lead: plans and delegates
    PLANNER = "planner"          # Decomposes goals into steps
    RESEARCHER = "researcher"    # Gathers information
    CODER = "coder"              # Writes/edits code
    REVIEWER = "reviewer"        # Critiques and validates
    TESTER = "tester"            # Verifies with tests/checks
    EXECUTOR = "executor"        # Runs tools and commands


class OrchestrationMode(str, Enum):
    """How agents coordinate."""

    SEQUENTIAL = "sequential"      # Chain: one after another
    PARALLEL = "parallel"          # Fan-out, gather results
    CONSENSUS = "consensus"        # Multiple agents, agree on best
    SUPERVISOR = "supervisor"      # Lead agent delegates and reviews


class AgentSpec(BaseModel):
    """Definition of a team member."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    role: AgentRole
    name: str = ""
    system_prompt: str = ""
    model_hint: str | None = None  # preferred model for this agent
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)

    @property
    def key(self) -> str:
        return self.role.value


class AgentMessage(BaseModel):
    """Message passed between agents."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    msg_id: str = Field(default_factory=lambda: str(uuid4())[:12])
    from_role: AgentRole
    to_role: AgentRole
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentResult(BaseModel):
    """Outcome of a single agent run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    role: AgentRole
    agent_name: str = ""
    output: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class ConsensusResult(BaseModel):
    """Aggregated result from a consensus run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    results: list[AgentResult] = Field(default_factory=list)
    agreed_output: str = ""
    agreement_count: int = 0
    confidence: float = 0.0

    def add(self, result: AgentResult) -> None:
        self.results.append(result)
        if result.ok:
            self.agreement_count += 1


class TeamRunResult(BaseModel):
    """Full result of an orchestrated team run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    mode: OrchestrationMode
    task: str
    messages: list[AgentMessage] = Field(default_factory=list)
    results: dict[str, AgentResult] = Field(default_factory=dict)
    final_output: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list)