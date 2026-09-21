"""
Phase 1 Tests: Config & Exceptions
"""
import pytest

from titan_agent.config_v2 import LLMSettings, SecuritySettings, Settings, get_settings
from titan_agent.exceptions import (
    ErrorCode,
    LLMError,
    PermissionError,
    RateLimitError,
    TitanError,
    ToolError,
    ToolNotFoundError,
    ToolTimeoutError,
    ValidationError,
    get_error_chain,
    is_retryable,
    wrap_error,
)


class TestSettings:
    """Test configuration loading"""
    
    def test_default_settings(self):
        s = Settings()
        assert s.app_name == "Titan Agent"
        assert s.environment == "development"
        assert s.llm.default_provider == "openrouter"
        assert s.security.max_command_timeout == 300
        assert s.monitoring.log_level == "INFO"
    
    def test_llm_settings(self):
        s = LLMSettings()
        assert s.default_provider == "openrouter"
        assert s.max_tokens == 4096
    
    def test_security_settings(self):
        s = SecuritySettings()
        assert "git" in s.allowed_commands
        assert "rm -rf" in s.blocked_commands
        assert s.max_command_timeout == 300
    
    def test_singleton_behavior(self):
        """get_settings should return cached instance"""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


class TestExceptions:
    """Test exception hierarchy"""
    
    def test_base_error(self):
        err = TitanError("test message", ErrorCode.VALIDATION_ERROR, {"field": "test"})
        assert err.code == ErrorCode.VALIDATION_ERROR
        assert err.details["field"] == "test"
        assert "[VALIDATION_ERROR] test message (field=test)" in str(err)
    
    def test_error_with_cause(self):
        try:
            raise ValueError("original error")
        except ValueError as e:
            err = TitanError("wrapped", ErrorCode.INTERNAL_ERROR, cause=e)
            assert err.cause is e
            assert isinstance(err.cause, ValueError)
    
    def test_validation_error(self):
        err = ValidationError("invalid email", field="email", value="bad")
        assert err.code == ErrorCode.VALIDATION_ERROR
        assert err.details["field"] == "email"
        assert err.details["value"] == "bad"
    
    def test_permission_error(self):
        err = PermissionError("no access", resource="file.txt", action="read", required_permission="file:read")
        assert err.code == ErrorCode.PERMISSION_DENIED
        assert err.details["resource"] == "file.txt"
        assert err.details["required_permission"] == "file:read"
    
    def test_rate_limit_error(self):
        err = RateLimitError("too many", limit=100, window=60, retry_after=30)
        assert err.code == ErrorCode.RATE_LIMITED
        assert err.details["limit"] == 100
        assert err.details["retry_after_seconds"] == 30
    
    def test_tool_error(self):
        err = ToolError("failed", tool_name="execute_command", args={"cmd": "ls"}, exit_code=1, stderr="not found")
        assert err.code == ErrorCode.TOOL_EXECUTION_FAILED
        assert err.details["tool"] == "execute_command"
        assert err.details["exit_code"] == 1
    
    def test_tool_not_found(self):
        err = ToolNotFoundError("unknown_tool", ["read_file", "write_file"])
        assert err.code == ErrorCode.TOOL_NOT_FOUND
        assert "unknown_tool" in err.details["tool"]
        assert "read_file" in err.details["available_tools"]
    
    def test_tool_timeout(self):
        err = ToolTimeoutError("slow_tool", 300)
        assert err.code == ErrorCode.TOOL_TIMEOUT
        assert err.details["timeout_seconds"] == 300
    
    def test_llm_error_codes(self):
        # Rate limited
        err = LLMError("rate limited", provider="openrouter", model="gpt-4", status_code=429)
        assert err.code == ErrorCode.LLM_RATE_LIMITED
        assert err.details["retryable"] is True
        
        # Auth failed
        err = LLMError("bad key", status_code=401)
        assert err.code == ErrorCode.LLM_AUTH_FAILED
        
        # Unavailable
        err = LLMError("down", retryable=True)
        assert err.code == ErrorCode.LLM_UNAVAILABLE
    
    def test_wrap_error(self):
        try:
            raise ValueError("original")
        except ValueError as e:
            wrapped = wrap_error(e, "wrapped", ErrorCode.INTERNAL_ERROR, {"extra": "data"})
            assert wrapped.code == ErrorCode.INTERNAL_ERROR
            assert wrapped.cause is not None
            assert wrapped.details["extra"] == "data"
    
    def test_is_retryable(self):
        # Retryable errors
        assert is_retryable(LLMError("rate limited", status_code=429))
        assert is_retryable(LLMError("down", retryable=True))
        assert is_retryable(TimeoutError())
        assert is_retryable(ConnectionError())
        
        # Non-retryable
        assert not is_retryable(ValidationError("bad input"))
        assert not is_retryable(PermissionError("denied"))
    
    def test_error_chain(self):
        try:
            try:
                raise ValueError("root")
            except ValueError as e:
                raise TitanError("middle", ErrorCode.INTERNAL_ERROR, cause=e)
        except TitanError as e:
            chain = get_error_chain(e)
            assert len(chain) == 2
            assert "INTERNAL_ERROR" in chain[0]
            assert "VALUEERROR" in chain[1].upper()


class TestWrapError:
    """Test wrap_error utility"""
    
    def test_wrap_titan_error(self):
        original = TitanError("original", ErrorCode.VALIDATION_ERROR)
        wrapped = wrap_error(original, "wrapped", ErrorCode.INTERNAL_ERROR, {"extra": "data"})
        assert wrapped is original  # Returns same instance
        assert wrapped.details["extra"] == "data"
    
    def test_wrap_regular_exception(self):
        try:
            raise ValueError("original")
        except ValueError as e:
            wrapped = wrap_error(e, "wrapped", ErrorCode.INTERNAL_ERROR)
            assert wrapped.code == ErrorCode.INTERNAL_ERROR
            assert "original" in wrapped.message
            assert isinstance(wrapped.cause, ValueError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])