"""
Phase 1: Structured Configuration with Pydantic Settings v2
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM Provider Configuration"""
    model_config = SettingsConfigDict(env_prefix="TITAN_LLM_", extra="ignore")
    
    default_provider: str = Field(default="openrouter", description="Default LLM provider")
    default_model: str = Field(default="gpt-4o-mini", description="Default model name")
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    temperature: float = Field(default=0.6, ge=0.0, le=2.0)
    request_timeout: int = Field(default=180, ge=10, le=600)
    
    # API Keys
    openrouter_api_key: str | None = Field(default=None, description="OpenRouter API key")
    groq_api_key: str | None = Field(default=None, description="Groq API key")
    deepseek_api_key: str | None = Field(default=None, description="DeepSeek API key")
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    openai_base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI base URL")
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama base URL")
    lmstudio_base_url: str = Field(default="http://localhost:1234", description="LM Studio base URL")
    completions_base_url: str = Field(default="https://completions.me", description="Completions.me base URL")
    completions_api_key: str | None = Field(default=None, description="Completions.me API key")
    omni_base_url: str = Field(default="http://localhost:20128/v1", description="OmniRoute gateway base URL")
    omni_api_key: str | None = Field(default=None, description="OmniRoute API key")
    omni_model: str = Field(default="auto", description="OmniRoute default model")


class SecuritySettings(BaseSettings):
    """Security & Permissions Configuration"""
    model_config = SettingsConfigDict(env_prefix="TITAN_SECURITY_", extra="ignore")
    
    # Command allowlist
    allowed_commands: list[str] = Field(
        default=["git", "npm", "python", "pip", "dir", "ls", "cat", "echo"],
        description="Allowed shell commands"
    )
    blocked_commands: list[str] = Field(
        default=["rm -rf", "format", "fdisk", "dd", "mkfs", "shutdown", "reboot"],
        description="Explicitly blocked commands"
    )
    
    # Execution limits
    max_command_timeout: int = Field(default=300, ge=10, le=3600)
    max_output_size: int = Field(default=10_000_000, ge=1000, le=100_000_000)
    max_parallel_tools: int = Field(default=10, ge=1, le=50)
    
    # Workspace isolation
    workspace_root: Path = Field(default=Path.cwd() / "workspace", description="Workspace root directory")
    allow_absolute_paths: bool = Field(default=False, description="Allow absolute paths outside workspace")
    
    # Rate limiting
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests: int = Field(default=100, ge=1, le=10000)
    rate_limit_window: int = Field(default=60, ge=1, le=3600)
    
    # Telegram
    telegram_enabled: bool = Field(default=False)
    telegram_api_id: str | None = None
    telegram_api_hash: str | None = None
    telegram_send_allowlist: list[str] = Field(default=[])


class MonitoringSettings(BaseSettings):
    """Monitoring & Observability Configuration"""
    model_config = SettingsConfigDict(env_prefix="TITAN_MONITORING_", extra="ignore")
    
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_format: str = Field(default="json", pattern="^(json|console)$")
    log_file: Path | None = Field(default=None)
    
    metrics_enabled: bool = Field(default=True)
    metrics_port: int = Field(default=9090, ge=1024, le=65535)
    
    # OpenTelemetry
    otlp_enabled: bool = Field(default=False)
    otlp_endpoint: str | None = Field(default=None)
    otlp_headers: dict[str, str] = Field(default_factory=dict)
    
    # Health checks
    health_check_interval: int = Field(default=30, ge=5, le=300)
    health_check_timeout: int = Field(default=5, ge=1, le=30)


class StorageSettings(BaseSettings):
    """Storage & Database Configuration"""
    model_config = SettingsConfigDict(env_prefix="TITAN_STORAGE_", extra="ignore")
    
    # SQLite
    db_path: Path = Field(default=Path.cwd() / "titan_memory.db")
    db_pool_size: int = Field(default=5, ge=1, le=20)
    db_max_overflow: int = Field(default=10, ge=0, le=50)
    db_echo: bool = Field(default=False)
    
    # Redis (for rate limiting, caching, sessions)
    redis_url: str | None = Field(default=None)
    redis_max_connections: int = Field(default=10, ge=1, le=100)
    redis_timeout: float = Field(default=5.0, ge=0.1, le=30.0)
    
    # File storage
    file_storage_path: Path = Field(default=Path.cwd() / "storage")
    max_file_size: int = Field(default=100_000_000, ge=1_000_000, le=1_000_000_000)
    allowed_extensions: list[str] = Field(default=[".txt", ".py", ".js", ".json", ".md", ".csv"])


class Settings(BaseSettings):
    """Main Application Settings - aggregates all sub-settings"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )
    
    llm: LLMSettings = Field(default_factory=LLMSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    
    # App metadata
    app_name: str = "Titan Agent"
    app_version: str = "1.0.0"
    environment: str = Field(default="development", pattern="^(development|staging|production)$")
    debug: bool = Field(default=False)
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        return v.lower()


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance - use this everywhere"""
    return Settings()


def reload_settings() -> Settings:
    """Force reload settings (useful for testing)"""
    get_settings.cache_clear()
    return get_settings()