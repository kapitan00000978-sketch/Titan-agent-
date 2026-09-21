"""
Base Interfaces for Reasoning Engine
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from .types import (
    Plan,
    PlanStep,
    ReasoningConfig,
    ReasoningStep,
    ReasoningTrace,
)


class ILLMProvider(ABC):
    """Interface for LLM providers"""
    
    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> AsyncGenerator[str, None] | str:
        """Generate completion from messages"""
    
    @abstractmethod
    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Generate completion with tool calling"""


class IToolExecutor(ABC):
    """Interface for tool execution"""
    
    @abstractmethod
    async def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a tool and return result"""
    
    @abstractmethod
    def get_available_tools(self) -> list[dict[str, Any]]:
        """Get list of available tools"""
    
    @abstractmethod
    def has_tool(self, name: str) -> bool:
        """Check if tool exists"""


class IReasoningEngine(ABC):
    """Base interface for reasoning engines"""
    
    @abstractmethod
    async def reason(
        self,
        task: str,
        config: ReasoningConfig | None = None,
        trace: ReasoningTrace | None = None,
    ) -> ReasoningTrace:
        """Execute reasoning for a task"""
    
    @abstractmethod
    async def stream_reason(
        self,
        task: str,
        config: ReasoningConfig | None = None,
    ) -> AsyncGenerator[ReasoningStep, None]:
        """Stream reasoning steps"""


class IPlanner(ABC):
    """Interface for planning engines"""
    
    @abstractmethod
    async def create_plan(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        available_tools: list[dict[str, Any]] | None = None,
    ) -> Plan:
        """Create an execution plan for a goal"""
    
    @abstractmethod
    async def replan(
        self,
        plan: Plan,
        failed_step: PlanStep | None = None,
        error: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> Plan:
        """Replan after failure or new information"""


class IReflector(ABC):
    """Interface for self-reflection/correction"""
    
    @abstractmethod
    async def reflect(
        self,
        trace: ReasoningTrace,
        focus: str | None = None,
    ) -> dict[str, Any]:
        """Reflect on reasoning trace, return insights/corrections"""
    
    @abstractmethod
    async def should_continue(
        self,
        trace: ReasoningTrace,
    ) -> tuple[bool, str]:
        """Decide if reasoning should continue, return (continue, reason)"""


class IEvaluator(ABC):
    """Interface for evaluating reasoning paths (for ToT)"""
    
    @abstractmethod
    async def evaluate(
        self,
        trace: ReasoningTrace,
        candidates: list[ReasoningTrace],
    ) -> list[float]:
        """Score candidate reasoning traces"""
    
    @abstractmethod
    async def is_solution(
        self,
        trace: ReasoningTrace,
        goal: str,
    ) -> tuple[bool, float]:
        """Check if trace solves the goal, return (is_solution, confidence)"""


class ReasoningContext:
    """Runtime context for reasoning execution"""
    
    def __init__(
        self,
        config: ReasoningConfig | None = None,
        llm: ILLMProvider | None = None,
        tools: IToolExecutor | None = None,
        planner: IPlanner | None = None,
        reflector: IReflector | None = None,
        evaluator: IEvaluator | None = None,
    ):
        self.config = config or ReasoningConfig()
        self.llm = llm
        self.tools = tools
        self.planner = planner
        self.reflector = reflector
        self.evaluator = evaluator
        self._step_count = 0
        self._reflection_count = 0
    
    def increment_step(self) -> int:
        self._step_count += 1
        return self._step_count
    
    def should_reflect(self) -> bool:
        if not self.config.enable_reflection:
            return False
        return self._step_count % self.config.reflection_interval == 0
    
    def can_reflect(self) -> bool:
        return self._reflection_count < self.config.max_reflection_turns
    
    def increment_reflection(self) -> None:
        self._reflection_count += 1