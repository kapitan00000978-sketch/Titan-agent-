"""
Phase 1: Dependency Injection Container & Execution Context
Provides proper inversion of control and request-scoped context.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import uuid4

from .config_v2 import Settings, get_settings
from .exceptions import (
    ErrorCode,
    PermissionError,
    TitanError,
)

T = TypeVar("T")


class ServiceRegistry:
    """
    Simple dependency injection container.
    Supports singletons, factories, and scoped instances.
    """
    
    def __init__(self):
        self._singletons: dict[type, Any] = {}
        self._factories: dict[type, Callable[..., Any]] = {}
        self._scoped: dict[type, Any] = {}
        self._scope_id: str | None = None
    
    def register_singleton(self, interface: type[T], instance: T) -> None:
        """Register a pre-created singleton instance"""
        self._singletons[interface] = instance
    
    def register_factory(self, interface: type[T], factory: Callable[..., Any]) -> None:
        """Register a factory function for creating instances"""
        self._factories[interface] = factory
    
    def get(self, interface: type[T]) -> T:
        """Get an instance (singleton or create from factory)"""
        if interface in self._singletons:
            return self._singletons[interface]
        
        if interface in self._factories:
            instance = self._factories[interface]()
            self._singletons[interface] = instance  # Cache as singleton
            return instance
        
        raise TitanError(
            f"No provider registered for {interface.__name__}",
            ErrorCode.CONFIGURATION_ERROR,
        )
    
    def get_or_none(self, interface: type[T]) -> T | None:
        """Get instance or return None"""
        try:
            return self.get(interface)
        except TitanError:
            return None
    
    # ============ Scoped Instances (per-request) ============
    
    def begin_scope(self, scope_id: str | None = None) -> str:
        """Begin a new scope (e.g., per-request)"""
        self._scope_id = scope_id or str(uuid4())
        self._scoped = {}
        return self._scope_id
    
    def end_scope(self) -> None:
        """End current scope"""
        self._scoped = {}
        self._scope_id = None
    
    def set_scoped(self, interface: type[T], instance: T) -> None:
        """Register an instance for current scope"""
        if not self._scope_id:
            raise TitanError("No active scope", ErrorCode.CONFIGURATION_ERROR)
        self._scoped[interface] = instance
    
    def get_scoped(self, interface: type[T]) -> T | None:
        """Get scoped instance"""
        return self._scoped.get(interface)
    
    def clear(self) -> None:
        """Clear all registrations"""
        self._singletons.clear()
        self._factories.clear()
        self._scoped.clear()


# Global registry instance
registry = ServiceRegistry()


@dataclass
class ExecutionContext:
    """
    Request-scoped execution context.
    Carries user identity, permissions, rate limiting, and tracing info.
    """
    # Identity
    session_id: str
    user_id: str | None = None
    client_ip: str | None = None
    user_agent: str | None = None
    
    # Permissions
    permissions: set[str] = field(default_factory=set)
    roles: set[str] = field(default_factory=set)
    
    # Rate limiting
    rate_limit_key: str = ""
    rate_limit_remaining: int = 100
    
    # Tracing
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    parent_span_id: str | None = None
    span_id: str = field(default_factory=lambda: str(uuid4())[:8])
    
    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deadline: datetime | None = None
    
    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Settings (injected)
    settings: Settings = field(default_factory=get_settings)
    
    def has_permission(self, permission: str) -> bool:
        """Check if context has a specific permission"""
        if "admin" in self.roles:
            return True
        if "*" in self.permissions:
            return True
        return permission in self.permissions
    
    def require_permission(self, permission: str) -> None:
        """Raise if permission not granted"""
        if not self.has_permission(permission):
            raise PermissionError(
                f"Permission denied: {permission}",
                resource=permission,
                action="execute",
                required_permission=permission,
            )
    
    def add_permission(self, permission: str) -> None:
        """Grant a permission"""
        self.permissions.add(permission)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value"""
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value"""
        return self.metadata.get(key, default)
    
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds"""
        return (datetime.now(timezone.utc) - self.started_at).total_seconds() * 1000
    
    def is_expired(self) -> bool:
        """Check if context has exceeded deadline"""
        if self.deadline:
            return datetime.now(timezone.utc) > self.deadline
        return False


@asynccontextmanager
async def execution_context(
    session_id: str,
    user_id: str | None = None,
    permissions: set[str] | None = None,
    roles: set[str] | None = None,
    deadline_seconds: int | None = None,
    **metadata,
) -> AsyncGenerator[ExecutionContext, None]:
    """
    Create an execution context with automatic scope management.
    
    Usage:
        async with execution_context("session-123", user_id="user-1") as ctx:
            result = await tool_registry.execute("read_file", {"path": "x.txt"}, ctx)
    """
    ctx = ExecutionContext(
        session_id=session_id,
        user_id=user_id,
        permissions=permissions or set(),
        roles=roles or set(),
        metadata=metadata,
    )
    
    if deadline_seconds:
        from datetime import timedelta
        ctx.deadline = datetime.now(timezone.utc) + timedelta(seconds=deadline_seconds)
    
    # Begin DI scope
    registry.begin_scope(ctx.trace_id)
    registry.set_scoped(ExecutionContext, ctx)
    registry.set_scoped(Settings, ctx.settings)
    
    try:
        yield ctx
    finally:
        registry.end_scope()


# ============ Service Provider Base Classes ============

class ServiceProvider:
    """Base class for service providers with lifecycle management"""
    
    def __init__(self, context: ExecutionContext | None = None):
        self.context = context
        self._started = False
    
    async def start(self) -> None:
        """Initialize the service"""
        if self._started:
            return
        await self._start()
        self._started = True
    
    async def stop(self) -> None:
        """Cleanup the service"""
        if not self._started:
            return
        await self._stop()
        self._started = False
    
    async def _start(self) -> None:
        """Override in subclass"""
    
    async def _stop(self) -> None:
        """Override in subclass"""
    
    @property
    def is_started(self) -> bool:
        return self._started


class LifecycleManager:
    """Manages startup/shutdown of all registered services"""
    
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self._services: list[ServiceProvider] = []
    
    def register(self, provider: ServiceProvider) -> None:
        self._services.append(provider)
    
    async def start_all(self) -> None:
        for svc in self._services:
            await svc.start()
    
    async def stop_all(self) -> None:
        for svc in reversed(self._services):
            await svc.stop()


# ============ Provider Functions ============

def configure_services() -> ServiceRegistry:
    """Configure all application services - call once at startup"""
    settings = get_settings()
    
    # Register settings as singleton
    registry.register_singleton(Settings, settings)
    
    # Register core services as factories
    # These will be implemented in Phase 2
    # registry.register_factory(LLMClient, lambda: LLMClient(settings.llm))
    # registry.register_factory(ToolRegistry, lambda: ToolRegistry(settings.security.workspace_root))
    # registry.register_factory(MemoryManager, lambda: MemoryManager(settings.storage.db_path))
    # registry.register_factory(MCPManager, lambda: MCPManager(settings.storage.file_storage_path / "mcp_servers.json"))
    
    return registry


async def get_context() -> ExecutionContext:
    """Get current execution context (must be within execution_context scope)"""
    ctx = registry.get_scoped(ExecutionContext)
    if not ctx:
        raise TitanError("No active execution context", ErrorCode.CONFIGURATION_ERROR)
    return ctx