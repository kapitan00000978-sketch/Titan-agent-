import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = Path(os.getenv("TITAN_WORKSPACE", str(BASE_DIR / "workspace")))
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Completions.me — free OpenAI-compatible gateway (Claude Opus/GPT-5/Gemini/Grok free)
COMPLETIONS_API_KEY = os.getenv("COMPLETIONS_API_KEY", "")
COMPLETIONS_BASE_URL = os.getenv("COMPLETIONS_BASE_URL", "https://completions.me/api/v1")
# Cheap frontier-class open-weight brains (2026 lineup): Kimi K3 (Moonshot),
# GLM-5.3 Flash (Zhipu) — both OpenAI-compatible endpoints.
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
KIMI_MODEL = os.getenv("KIMI_MODEL", "kimi-k3")
GLM_API_KEY = os.getenv("GLM_API_KEY", "")
GLM_BASE_URL = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
GLM_MODEL = os.getenv("GLM_MODEL", "glm-5.3-flash")
# OmniRoute — self-hosted AI gateway (localhost:20128) with smart auto-routing
# virtual models: auto, auto/coding, auto/fast, auto/smart, auto/offline, auto/cheap.
# It routes each request to the best available provider/model automatically.
OMNI_API_KEY = os.getenv("OMNI_API_KEY", "")
OMNI_BASE_URL = os.getenv("OMNI_BASE_URL", "http://localhost:20128/v1")
OMNI_MODEL = os.getenv("OMNI_MODEL", "auto")
OMNI_AUTO_MODELS = ("auto", "auto/coding", "auto/fast", "auto/smart", "auto/offline", "auto/cheap")

# If an API key is present, default to that provider; otherwise seamlessly use local Ollama!
# Precedence: OpenRouter -> OmniRoute -> Kimi K3 -> GLM-5.3 Flash -> DeepSeek -> Groq -> OpenAI -> Ollama.
if OPENROUTER_API_KEY:
    DEFAULT_PROVIDER = os.getenv("TITAN_PROVIDER", "openrouter")
    DEFAULT_MODEL = os.getenv("TITAN_MODEL", "nousresearch/hermes-3-llama-3.1-405b:free")
elif OMNI_API_KEY:
    DEFAULT_PROVIDER = os.getenv("TITAN_PROVIDER", "omni")
    DEFAULT_MODEL = os.getenv("TITAN_MODEL", OMNI_MODEL)
elif KIMI_API_KEY:
    DEFAULT_PROVIDER = os.getenv("TITAN_PROVIDER", "kimi")
    DEFAULT_MODEL = os.getenv("TITAN_MODEL", KIMI_MODEL)
elif GLM_API_KEY:
    DEFAULT_PROVIDER = os.getenv("TITAN_PROVIDER", "glm")
    DEFAULT_MODEL = os.getenv("TITAN_MODEL", GLM_MODEL)
elif DEEPSEEK_API_KEY:
    DEFAULT_PROVIDER = os.getenv("TITAN_PROVIDER", "deepseek")
    DEFAULT_MODEL = os.getenv("TITAN_MODEL", "deepseek-chat")
elif GROQ_API_KEY:
    DEFAULT_PROVIDER = os.getenv("TITAN_PROVIDER", "groq")
    DEFAULT_MODEL = os.getenv("TITAN_MODEL", "llama-3.3-70b-versatile")
elif OPENAI_API_KEY:
    DEFAULT_PROVIDER = os.getenv("TITAN_PROVIDER", "openai")
    DEFAULT_MODEL = os.getenv("TITAN_MODEL", "gpt-4o")
else:
    # Default to Local Ollama hermes3:8b directly installed on user's machine!
    DEFAULT_PROVIDER = os.getenv("TITAN_PROVIDER", "ollama")
    DEFAULT_MODEL = os.getenv("TITAN_MODEL", "hermes3:8b")

# ---- Phase 13: provider fallback chain -------------------------------
# When the primary LLM provider fails with a network / rate-limit / server
# error (or is not configured), `LLMClient.chat_completion` automatically
# re-runs the request against the next provider from this chain. Read at CALL
# time (not import time) so tests and the runtime can change it on the fly.
#   TITAN_PROVIDER_FALLBACK_CHAIN="kimi,glm,deepseek,ollama"   (comma-separated)
#   TITAN_PROVIDER_FALLBACK_MODELS="kimi=my-kimi-model,glm=my-glm-model"
#   (optional per-provider model overrides, provider=model pairs)
def provider_fallback_chain() -> list[str]:
    """Ordered provider names to try after the primary, in priority order."""
    raw = os.getenv("TITAN_PROVIDER_FALLBACK_CHAIN", "")
    return [p.strip() for p in raw.split(",") if p.strip()]


def provider_fallback_models() -> dict[str, str]:
    """Per-provider model overrides for the fallback chain."""
    overrides: dict[str, str] = {}
    for pair in os.getenv("TITAN_PROVIDER_FALLBACK_MODELS", "").split(","):
        if "=" in pair:
            provider, _, model = pair.partition("=")
            provider, model = provider.strip(), model.strip()
            if provider and model:
                overrides[provider] = model
    return overrides


def provider_default_model(provider: str) -> str | None:
    """Known default model for a provider when the fallback chain names it."""
    return {
        "openrouter": "nousresearch/hermes-3-llama-3.1-405b:free",
        "kimi": KIMI_MODEL,
        "glm": GLM_MODEL,
        "omni": OMNI_MODEL,
        "deepseek": "deepseek-chat",
        "groq": "llama-3.3-70b-versatile",
        "openai": "gpt-4o",
        "ollama": "hermes3:8b",
        "completions": "claude-opus-4-1-20250817",
        "lmstudio": "local-model",
    }.get(provider)

# MCP Config Path
MCP_CONFIG_FILE = BASE_DIR / "mcp_servers.json"

# Web Server Settings
SERVER_HOST = os.getenv("TITAN_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("TITAN_PORT", "7860"))

# Agent Autonomy Settings
AUTONOMOUS_MODE = os.getenv("TITAN_AUTONOMOUS", "true").lower() in ("true", "1", "yes")
MAX_ITERATIONS = int(os.getenv("TITAN_MAX_ITERATIONS", "25"))

# ---- Phase 7: Full Autonomy — dynamic step budget (no hard 48 clamp) ----
# TITAN_STEP_CAP: the ceiling applied after effort scaling (default 48, was hardcoded).
# TITAN_UNLIMITED_STEPS=1 (or true/yes) removes the ceiling entirely — the agent
# keeps iterating until the task is provably done (safety: it still must VERIFY
# and produce a final answer; it just may take more steps).
MAX_STEPS_CAP = int(os.getenv("TITAN_STEP_CAP", "48"))
UNLIMITED_STEPS = os.getenv("TITAN_UNLIMITED_STEPS", "0").strip().lower() in ("1", "true", "yes")
# Deep modes' extra budget base (was hardcoded at 40).
DEEP_MAX_STEPS_BASE = int(os.getenv("TITAN_DEEP_MAX_STEPS", "40"))
# ---- Phase 7: autonomous task queue / daemon ----
TASK_QUEUE_FILE = Path(os.getenv("TITAN_TASK_QUEUE", str(WORKSPACE_DIR / "task_queue.db")))
DAEMON_POLL_INTERVAL = float(os.getenv("TITAN_DAEMON_INTERVAL", "5.0"))
DAEMON_MAX_CONCURRENT = int(os.getenv("TITAN_DAEMON_CONCURRENCY", "1"))

# Token throughput guardrail: the agent never exceeds this many tokens/second
# (token bucket). 214,000/s is effectively invisible in production but fully
# enforced for every LLM call (backend providers and the Puter browser path).
TOKEN_RATE_LIMIT_PER_SEC = int(os.getenv("TITAN_TOKEN_RATE_LIMIT", "214000"))

# ---- Phase 10: harness hardening -----------------------------------------
# In-run message budget in characters. When the living context of a run exceeds
# it, the oldest tool rounds are trimmed (whole assistant->tool blocks) so long
# / deep runs never blow the provider window. Rough heuristic: 1 token ~= 4 chars.
CONTEXT_BUDGET_CHARS = int(os.getenv("TITAN_CONTEXT_BUDGET_CHARS", "200000"))
# Bounded retries for TRANSIENT LLM network errors only (aiohttp.ClientError /
# OSError / timeouts). API-level failures (401/403/...) and context-length
# errors that trimming cannot fix still fail fast. 0 disables retries.
LLM_TRANSIENT_RETRIES = int(os.getenv("TITAN_LLM_TRANSIENT_RETRIES", "2"))

# ---- Phase 8: FULL ACCESS — remove every capability boundary ----
# TITAN_FULL_ACCESS=1    -> step caps lifted, tool/command timeouts raised,
#                           approval gates auto-granted, download size cap and
#                           HTTP-server port range removed, token rate-limiter
#                           disabled, structured-reasoning step clamp lifted.
# TITAN_ABSOLUTE_ACCESS=1 -> additionally lifts the two protection lines that
#                           even FULL_ACCESS keeps: the destructive-command
#                           deny floor (rm -rf / format / mkfs / shutdown) and
#                           the SSRF private-network guard. Implies FULL_ACCESS.
# Both can be toggled at runtime (web UI / API / CLI) via set_full_access().
_FULL_ACCESS_OVERRIDE: bool | None = None


def _env_flag(name: str) -> bool:
    return os.getenv(name, "0").strip().lower() in ("1", "true", "yes")


def full_access_enabled() -> bool:
    """True when FULL (or ABSOLUTE) access is active.

    Every limit site calls this at call-time (not import-time) so a mid-run
    toggle takes effect immediately. The module override wins over the env.
    """
    if _FULL_ACCESS_OVERRIDE is not None:
        return _FULL_ACCESS_OVERRIDE
    return _env_flag("TITAN_FULL_ACCESS") or _env_flag("TITAN_ABSOLUTE_ACCESS")


def absolute_access_enabled() -> bool:
    """True only in ABSOLUTE mode — the destructive-deny floor and SSRF guard
    are ALSO lifted (the last two protection lines)."""
    if _FULL_ACCESS_OVERRIDE is not None:
        return _FULL_ACCESS_OVERRIDE
    return _env_flag("TITAN_ABSOLUTE_ACCESS")


def set_full_access(on: bool | None) -> None:
    """Runtime toggle (web UI / API / CLI) — no process restart needed.

    ``True``/``False`` force the mode on/off; ``None`` clears the override so
    the environment variables govern again (used to reset between tests).
    """
    global _FULL_ACCESS_OVERRIDE
    _FULL_ACCESS_OVERRIDE = None if on is None else bool(on)

# ---- Telegram account manager (opt-in, consent-gated) ----
# TITAN_TELEGRAM_ENABLED must be 'true' for ANY Telegram tool to work.
# API creds come from https://my.telegram.org -> API development tools.
# Sending is only allowed to targets listed in TITAN_TELEGRAM_SEND_ALLOWLIST
# (comma-separated usernames or ids); empty = read-only.
TITAN_TELEGRAM_ENABLED = os.getenv("TITAN_TELEGRAM_ENABLED", "false").lower() in ("true", "1", "yes")
TITAN_TELEGRAM_API_ID = os.getenv("TITAN_TELEGRAM_API_ID", "")
TITAN_TELEGRAM_API_HASH = os.getenv("TITAN_TELEGRAM_API_HASH", "")
TITAN_TELEGRAM_SEND_ALLOWLIST = os.getenv("TITAN_TELEGRAM_SEND_ALLOWLIST", "")
