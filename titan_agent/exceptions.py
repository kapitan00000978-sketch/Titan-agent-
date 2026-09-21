"""
Phase 1: Custom Exception Hierarchy
Enterprise-grade error handling with codes, details, and proper chaining.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """Standardized error codes for programmatic handling"""
    
    # Generic
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    
    # Permissions
    PERMISSION_DENIED = "PERMISSION_DENIED"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    
    # Tools
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    TOOL_INVALID_ARGS = "TOOL_INVALID_ARGS"
    DUPLICATE_TOOL = "DUPLICATE_TOOL"
    
    # LLM
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    LLM_INVALID_RESPONSE = "LLM_INVALID_RESPONSE"
    LLM_RATE_LIMITED = "LLM_RATE_LIMITED"
    LLM_AUTH_FAILED = "LLM_AUTH_FAILED"
    LLM_CONTEXT_TOO_LONG = "LLM_CONTEXT_TOO_LONG"
    
    # MCP
    MCP_SERVER_UNAVAILABLE = "MCP_SERVER_UNAVAILABLE"
    MCP_TOOL_NOT_FOUND = "MCP_TOOL_NOT_FOUND"
    MCP_CONNECTION_FAILED = "MCP_CONNECTION_FAILED"
    
    # Storage
    STORAGE_ERROR = "STORAGE_ERROR"
    STORAGE_NOT_FOUND = "STORAGE_NOT_FOUND"
    STORAGE_QUOTA_EXCEEDED = "STORAGE_QUOTA_EXCEEDED"
    DATABASE_ERROR = "DATABASE_ERROR"
    
    # Network
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    CONNECTION_REFUSED = "CONNECTION_REFUSED"
    
    # Validation
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_PATH = "INVALID_PATH"
    INVALID_COMMAND = "INVALID_COMMAND"
    COMMAND_BLOCKED = "COMMAND_BLOCKED"
    
    # External Services
    MCP_SERVER_DOWN = "MCP_SERVER_DOWN"
    TELEGRAM_ERROR = "TELEGRAM_ERROR"
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"


class TitanError(Exception):
    """
    Base exception for all Titan Agent errors.
    
    Attributes:
        message: Human-readable error message
        code: Machine-readable error code
        details: Additional structured details
        cause: Original exception that caused this error
    """
    
    def __init__(
        self,
        message: str,
        code: ErrorCode | str = ErrorCode.UNKNOWN_ERROR,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ):
        self.message = message
        self.code = ErrorCode(code) if isinstance(code, str) else code
        self.details = details or {}
        self.cause = cause
        
        # Build comprehensive message
        parts = [f"[{self.code.value}] {message}"]
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            parts.append(f"({details_str})")
        
        super().__init__(" ".join(parts))
    
    def __str__(self) -> str:
        parts = [f"[{self.code.value}] {self.message}"]
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            parts.append(f"({details_str})")
        return " ".join(parts)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code.value}, message={self.message!r}, details={self.details})"
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses / logging"""
        return {
            "error": self.__class__.__name__,
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
        }
    
    def add_detail(self, key: str, value: Any) -> TitanError:
        """Fluent API for adding details"""
        self.details[key] = value
        return self
    
    def with_cause(self, cause: BaseException) -> TitanError:
        """Set the root cause"""
        self.cause = cause
        return self


# ============ Specific Exception Types ============

class ConfigurationError(TitanError):
    """Configuration/initialization errors"""
    def __init__(self, message: str, details: dict | None = None, cause: BaseException | None = None):
        super().__init__(message, ErrorCode.CONFIGURATION_ERROR, details, cause)


class ValidationError(TitanError):
    """Input validation errors"""
    def __init__(self, message: str, field: str | None = None, value: Any = None, cause: BaseException | None = None):
        details = {"field": field} if field else {}
        if value is not None:
            details["value"] = str(value)[:100]
        super().__init__(message, ErrorCode.VALIDATION_ERROR, details, cause)


class PermissionError(TitanError):
    """Permission/authorization errors"""
    def __init__(
        self,
        message: str,
        resource: str | None = None,
        action: str | None = None,
        required_permission: str | None = None,
        cause: BaseException | None = None,
    ):
        details = {}
        if resource: details["resource"] = resource
        if action: details["action"] = action
        if required_permission: details["required_permission"] = required_permission
        super().__init__(message, ErrorCode.PERMISSION_DENIED, details, cause)


class RateLimitError(TitanError):
    """Rate limiting errors"""
    def __init__(
        self,
        message: str,
        limit: int | None = None,
        window: int | None = None,
        retry_after: int | None = None,
        cause: BaseException | None = None,
    ):
        details = {}
        if limit: details["limit"] = limit
        if window: details["window_seconds"] = window
        if retry_after: details["retry_after_seconds"] = retry_after
        super().__init__(message, ErrorCode.RATE_LIMITED, details, cause)


class ToolError(TitanError):
    """Tool execution errors"""
    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        args: dict | None = None,
        exit_code: int | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        cause: BaseException | None = None,
        details: dict | None = None,
    ):
        auto_details = {}
        if tool_name: auto_details["tool"] = tool_name
        if args: auto_details["args"] = {k: str(v)[:100] for k, v in args.items()}
        if exit_code is not None: auto_details["exit_code"] = exit_code
        if stdout: auto_details["stdout"] = stdout[:500]
        if stderr: auto_details["stderr"] = stderr[:500]
        if details:
            auto_details.update(details)
        super().__init__(message, ErrorCode.TOOL_EXECUTION_FAILED, auto_details, cause)


class ToolNotFoundError(ToolError):
    """Tool not registered"""
    def __init__(self, tool_name: str, available_tools: list[str] | None = None):
        details = {"tool": tool_name}
        if available_tools:
            details["available_tools"] = available_tools
        super().__init__(
            f"Tool '{tool_name}' not found",
            tool_name=tool_name,
            details=details,
        )
        self.code = ErrorCode.TOOL_NOT_FOUND


class ToolTimeoutError(ToolError):
    """Tool execution timeout"""
    def __init__(self, tool_name: str, timeout: int, cause: BaseException | None = None):
        super().__init__(
            f"Tool '{tool_name}' timed out after {timeout}s",
            tool_name=tool_name,
            details={"timeout_seconds": timeout},
            cause=cause,
        )
        self.code = ErrorCode.TOOL_TIMEOUT


class LLMError(TitanError):
    """LLM-related errors"""
    def __init__(
        self,
        message: str,
        provider: str | None = None,
        model: str | None = None,
        status_code: int | None = None,
        retryable: bool = False,
        cause: BaseException | None = None,
    ):
        details = {}
        if provider: details["provider"] = provider
        if model: details["model"] = model
        if status_code: details["status_code"] = status_code
        
        code = ErrorCode.LLM_UNAVAILABLE
        if status_code == 429:
            code = ErrorCode.LLM_RATE_LIMITED
            retryable = True
        elif status_code in (401, 403):
            code = ErrorCode.LLM_AUTH_FAILED
        elif retryable:
            code = ErrorCode.LLM_UNAVAILABLE
            
        details["retryable"] = retryable
        super().__init__(message, code, details, cause)


class MCPError(TitanError):
    """MCP server errors"""
    def __init__(
        self,
        message: str,
        server_name: str | None = None,
        tool_name: str | None = None,
        cause: BaseException | None = None,
    ):
        details = {}
        if server_name: details["server"] = server_name
        if tool_name: details["tool"] = tool_name
        super().__init__(message, ErrorCode.MCP_SERVER_UNAVAILABLE, details, cause)


class StorageError(TitanError):
    """Storage/database errors"""
    def __init__(
        self,
        message: str,
        operation: str | None = None,
        path: str | None = None,
        cause: BaseException | None = None,
    ):
        details = {}
        if operation: details["operation"] = operation
        if path: details["path"] = path
        super().__init__(message, ErrorCode.STORAGE_ERROR, details, cause)


class DatabaseError(StorageError):
    """Database-specific errors"""
    def __init__(
        self,
        message: str,
        query: str | None = None,
        params: tuple | None = None,
        cause: BaseException | None = None,
    ):
        details = {}
        if query: details["query"] = query[:200]
        if params: details["params"] = str(params)[:200]
        super().__init__(message, operation="database", details=details, cause=cause)
        self.code = ErrorCode.DATABASE_ERROR


# ============ Utility Functions ============

def wrap_error(
    error: BaseException,
    message: str,
    code: ErrorCode | str = ErrorCode.UNKNOWN_ERROR,
    details: dict | None = None,
) -> TitanError:
    """Wrap any exception into a TitanError with context"""
    if isinstance(error, TitanError):
        error.details.update(details or {})
        return error
    
    return TitanError(
        message=f"{message}: {error}",
        code=code,
        details=details,
        cause=error,
    )


def is_retryable(error: BaseException) -> bool:
    """Check if an error is retryable"""
    if isinstance(error, TitanError):
        if error.code in (
            ErrorCode.LLM_RATE_LIMITED,
            ErrorCode.LLM_UNAVAILABLE,
            ErrorCode.NETWORK_ERROR,
            ErrorCode.TIMEOUT,
            ErrorCode.CONNECTION_REFUSED,
            ErrorCode.MCP_SERVER_UNAVAILABLE,
        ):
            return True
        return error.details.get("retryable", False)
    
    # Network/timeout errors are generally retryable
    retryable_types = (
        TimeoutError,
        ConnectionError,
        ConnectionRefusedError,
        ConnectionResetError,
    )
    return isinstance(error, retryable_types)


def get_error_chain(error: BaseException) -> list[str]:
    """Get full error chain for logging"""
    chain = []
    current = error
    while current:
        if isinstance(current, TitanError):
            chain.append(f"[{current.code.value}] {current.message}")
        else:
            chain.append(f"[{type(current).__name__}] {current}")
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return chain