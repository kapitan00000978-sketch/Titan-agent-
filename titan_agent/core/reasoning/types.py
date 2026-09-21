"""
Core Reasoning Types - Foundation for ReAct, Plan-and-Execute, Tree of Thoughts
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class StepStatus(str, Enum):
    """Status of a reasoning step"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ActionType(str, Enum):
    """Type of action in reasoning"""
    THINK = "think"           # Internal reasoning
    ACT = "act"               # Tool execution
    OBSERVE = "observe"       # Tool result observation
    REFLECT = "reflect"       # Self-correction
    PLAN = "plan"             # Planning step
    DECIDE = "decide"         # Decision point


T = TypeVar("T")


class ReasoningStep(BaseModel):
    """Single step in a reasoning trace"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    step_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    step_number: int = 0
    action_type: ActionType = ActionType.THINK
    content: str = ""
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: Any | None = None
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def duration_ms(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None
    
    def is_terminal(self) -> bool:
        return self.status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED)


class PlanStep(BaseModel):
    """Single step in a plan"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    step_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    description: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    expected_outcome: str = ""
    dependencies: list[str] = Field(default_factory=list)  # step_ids this depends on
    status: StepStatus = StepStatus.PENDING
    result: Any | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3


class Plan(BaseModel):
    """Execution plan with multiple steps"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    plan_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    goal: str
    steps: list[PlanStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def add_step(self, step: PlanStep) -> None:
        self.steps.append(step)
        self.updated_at = datetime.now(timezone.utc)
    
    def get_ready_steps(self) -> list[PlanStep]:
        """Get steps that are ready to execute (dependencies met)"""
        ready = []
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue
            deps_met = all(
                any(s.step_id == dep and s.status == StepStatus.COMPLETED 
                    for s in self.steps)
                for dep in step.dependencies
            )
            if deps_met:
                ready.append(step)
        return ready
    
    def is_complete(self) -> bool:
        return all(s.status == StepStatus.COMPLETED for s in self.steps)
    
    def has_failed(self) -> bool:
        return any(s.status == StepStatus.FAILED and s.retry_count >= s.max_retries 
                   for s in self.steps)


class ReasoningTrace(BaseModel):
    """Complete reasoning trace for a task"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    trace_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    task: str
    steps: list[ReasoningStep] = Field(default_factory=list)
    plan: Plan | None = None
    final_answer: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    total_tokens: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def add_step(self, step: ReasoningStep) -> None:
        step.step_number = len(self.steps) + 1
        self.steps.append(step)
    
    def get_last_step(self) -> ReasoningStep | None:
        return self.steps[-1] if self.steps else None
    
    def get_steps_by_type(self, action_type: ActionType) -> list[ReasoningStep]:
        return [s for s in self.steps if s.action_type == action_type]
    
    def total_duration_ms(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return sum(s.duration_ms() or 0 for s in self.steps)
    
    def is_complete(self) -> bool:
        return self.final_answer is not None or (
            self.plan is not None and self.plan.is_complete()
        )


class ReasoningConfig(BaseModel):
    """Configuration for reasoning engine"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # ReAct settings
    max_steps: int = Field(default=20, ge=1, le=100)
    max_thinking_tokens: int = Field(default=2000, ge=100, le=10000)
    max_observation_tokens: int = Field(default=5000, ge=100, le=20000)
    
    # Plan-and-Execute settings
    max_plan_steps: int = Field(default=15, ge=1, le=50)
    max_retries_per_step: int = Field(default=3, ge=0, le=10)
    replan_on_failure: bool = True
    
    # Reflection settings
    enable_reflection: bool = True
    reflection_interval: int = Field(default=3, ge=1, le=10)  # reflect every N steps
    max_reflection_turns: int = Field(default=2, ge=1, le=5)
    
    # Tree of Thoughts settings
    tot_branching_factor: int = Field(default=3, ge=2, le=5)
    tot_max_depth: int = Field(default=3, ge=1, le=5)
    tot_evaluator_model: str | None = None  # Separate evaluator model
    
    # General
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    enable_streaming: bool = True
    verbose: bool = False