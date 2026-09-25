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
OMNI_API_KEY = os.getenv("OMNI_API_KEY", "")
OMNI_BASE_URL = os.getenv("OMNI_BASE_URL", "http://localhost:20128/v1")
OMNI_MODEL = os.getenv("OMNI_MODEL", "auto")
OMNI_AUTO_MODELS = ("auto", "auto/coding", "auto/fast", "auto/smart", "auto/offline", "auto/cheap")


# Additional Free Tier API Key Providers:
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")

SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY", "")
SAMBANOVA_BASE_URL = os.getenv("SAMBANOVA_BASE_URL", "https://api.sambanova.ai/v1")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_MODELS_BASE_URL = os.getenv("GITHUB_MODELS_BASE_URL", "https://models.inference.ai.azure.com")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_BASE_URL = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")

HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
HUGGINGFACE_BASE_URL = os.getenv("HUGGINGFACE_BASE_URL", "https://api-inference.huggingface.co/v1")

# Default provider resolution:
env_provider = os.getenv("TITAN_PROVIDER")
env_model = os.getenv("TITAN_MODEL")

if env_provider:
    DEFAULT_PROVIDER = env_provider
    DEFAULT_MODEL = env_model or ("gpt-4o" if env_provider == "g4f" else ("auto" if env_provider == "omni" else "hermes3:8b"))
elif OPENROUTER_API_KEY:
    DEFAULT_PROVIDER = "openrouter"
    DEFAULT_MODEL = "nousresearch/hermes-3-llama-3.1-405b:free"
elif DEEPSEEK_API_KEY:
    DEFAULT_PROVIDER = "deepseek"
    DEFAULT_MODEL = "deepseek-chat"
elif GROQ_API_KEY:
    DEFAULT_PROVIDER = "groq"
    DEFAULT_MODEL = "llama-3.3-70b-versatile"
elif OPENAI_API_KEY:
    DEFAULT_PROVIDER = "openai"
    DEFAULT_MODEL = "gpt-4o"
elif KIMI_API_KEY:
    DEFAULT_PROVIDER = "kimi"
    DEFAULT_MODEL = KIMI_MODEL
elif GLM_API_KEY:
    DEFAULT_PROVIDER = "glm"
    DEFAULT_MODEL = GLM_MODEL
elif OMNI_API_KEY:
    DEFAULT_PROVIDER = "omni"
    DEFAULT_MODEL = OMNI_MODEL
else:
    # Default to Local Ollama (100% private, reliable, and official).
    # To use experimental reverse-proxies (g4f/tgpt), set TITAN_PROVIDER=g4f or tgpt explicitly.
    DEFAULT_PROVIDER = "ollama"
    DEFAULT_MODEL = "hermes3:8b"

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
        "gemini": "gemini-2.0-flash",
        "sambanova": "Meta-Llama-3.3-70B-Instruct",
        "github": "gpt-4o",
        "mistral": "codestral-latest",
        "huggingface": "meta-llama/Llama-3.2-3B-Instruct",
    }.get(provider)

# ---- Phase 17: bounded parallel tool execution -------------------------
# Tool calls produced in one model turn run concurrently, but capped by the
# semaphore below so terminal-heavy batches stay predictable. 1 = fully serial.
# With TITAN_CANCEL_ON_TOOL_ERROR=1 the batch stops as soon as any tool fails
# and the remaining in-flight calls are cancelled (useful when later tools
# consume earlier outputs). Both are read at CALL time (not import time) so
# tests and the runtime can tune them on the fly.
def parallel_tool_calls() -> int:
    """Max tool executions running concurrently within a single model turn."""
    try:
        return max(1, int(os.getenv("TITAN_PARALLEL_TOOL_CALLS", "4")))
    except (TypeError, ValueError):
        return 4


def cancel_on_tool_error() -> bool:
    """Cancel remaining in-flight tool calls as soon as any tool fails."""
    return os.getenv("TITAN_CANCEL_ON_TOOL_ERROR", "0").strip().lower() in (
        "1", "true", "yes"
    )


# ---- Phase 20: grounded final validation ----------------------------------
# A model that produces a final answer WITHOUT ever touching a tool is the
# classic hallucination path for weak local models (hermes3:8b etc.). When
# enabled (default 1), the run gives such answers ONE forced verification
# turn before finalizing: the model may emit tool calls (which execute and
# the loop continues) or explicitly decline with NO_TOOLS_NEEDED for pure
# conceptual tasks. Tool-using runs never pay for this call.
def final_grounding_enabled() -> bool:
    """Give zero-tool final answers one forced verification pass."""
    return os.getenv("TITAN_FINAL_GROUNDING", "1").strip().lower() in (
        "1", "true", "yes"
    )


# ---- Phase 21: dedicated reviewer model + bounded refinement --------------
# The critic/reflection pass that polishes final answers normally runs on the
# SAME model that generated them. When a separate reviewer is configured
# (TITAN_REVIEWER_PROVIDER / TITAN_REVIEWER_MODEL — e.g. a stronger cloud model
# while the generator runs a cheap local one), the reflection uses the
# reviewer, and the run spends up to TITAN_REFINEMENT_ROUNDS regenerations on
# the GENERATOR addressed to the reviewer's critique ("generate -> strong
# critique -> revise"). Both are opt-in: with no reviewer configured the
# reflection behaves exactly as before (refinement rounds have no effect).
def reviewer_model() -> tuple[str | None, str | None]:
    """(provider, model) of the dedicated reviewer LLM, if configured."""
    provider = os.getenv("TITAN_REVIEWER_PROVIDER", "").strip() or None
    model = os.getenv("TITAN_REVIEWER_MODEL", "").strip() or None
    return provider, model


def refinement_rounds() -> int:
    """Max generator revision rounds against the reviewer's critique
    (applies only when a dedicated reviewer is in play)."""
    try:
        return max(0, int(os.getenv("TITAN_REFINEMENT_ROUNDS", "1")))
    except (TypeError, ValueError):
        return 1


# ---- Phase 22: per-tool telemetry ------------------------------------------
# Tool execution stats are ALWAYS recorded (silent, requires nothing), but
# surfacing them inside the system prompt is opt-in: with TITAN_TOOL_RECORD=1
# tools that failed repeatedly in recent runs are listed so the model adapts
# instead of retrying a broken pattern. Off by default -> prompt stays stable.
def tool_record_enabled() -> bool:
    """Inject the adaptive TOOL RECORD block into future system prompts."""
    return os.getenv("TITAN_TOOL_RECORD", "0").strip().lower() in (
        "1", "true", "yes"
    )


# ---- Phase 23: repeated tool-failure guard (harness-level anti-retry-loop) --
# Weak models keep re-sending the SAME failing tool call with the SAME
# arguments, burning tokens and repeating the same dead end. The harness
# tracks identical (tool, canonical-args) patterns that already failed within
# a run and BLOCKS the next identical attempt, telling the model to change
# approach instead. Execution happens `TITAN_REPEAT_GUARD_LIMIT` times, then
# identical retries are skipped.
def repeat_guard_enabled() -> bool:
    """Block identical repeated failing tool calls (default on)."""
    return os.getenv("TITAN_REPEAT_GUARD", "1").strip().lower() in (
        "1", "true", "yes"
    )


def repeat_guard_limit() -> int:
    """How many identical failures are tolerated before blocking."""
    try:
        return max(1, int(os.getenv("TITAN_REPEAT_GUARD_LIMIT", "2")))
    except (TypeError, ValueError):
        return 2


# ---- Phase 24: task re-anchoring after context compaction ------------------
# Long runs lose the original objective when old messages get compacted,
# especially with small models. When compaction actually drops messages, a
# compact system reminder re-pins the ORIGINAL TASK right before the next
# model call. Only fires when compaction happened, so short runs are
# byte-for-byte unchanged.
def objective_reanchor_enabled() -> bool:
    """Re-pin the original task in the prompt after context compaction."""
    return os.getenv("TITAN_TASK_REANCHOR", "1").strip().lower() in (
        "1", "true", "yes"
    )


# ---- Phase 26: bounded auto post-check for edit runs ------------------------
# After a run that actually WROTE or EDITED files, one extra bounded model
# iteration is injected before finalizing: re-read the changed files, run the
# relevant verification, and only then ship the final answer. Bounded to one
# pass per run and only fires when write/edit tools were used, so read-only
# runs are byte-for-byte unchanged.
def auto_postcheck_enabled() -> bool:
    """Verify edited files + tests before finalizing (default on)."""
    return os.getenv("TITAN_AUTO_POSTCHECK", "1").strip().lower() in (
        "1", "true", "yes"
    )


# ---- Phase 30: empty final-answer guard --------------------------------------
# Weak models occasionally end a run with whitespace-only content — the run
# "succeeds" while telling the user nothing. When the candidate final is empty,
# the harness asks ONCE for the answer (bounded single retry), and if the model
# still returns nothing the final answer is an explicit notice instead of a
# silent empty success.
def empty_final_guard_enabled() -> bool:
    """Retry once on whitespace-only final answers (default on)."""
    return os.getenv("TITAN_EMPTY_FINAL_GUARD", "1").strip().lower() in (
        "1", "true", "yes"
    )


# ---- Phase 33: repeated malformed-arguments guard ----------------------------
# Tool calls whose arguments cannot be parsed as valid JSON are skipped (they
# must never run with empty arguments). But weak models re-send THE SAME
# malformed call over and over, burning turns. The harness counts skipped
# malformed calls per tool name within a run and, after
# `TITAN_MALFORMED_GUARD_LIMIT` name-level skips, BLOCKS further malformed
# calls from that tool with actionable guidance.
def malformed_guard_enabled() -> bool:
    """Block repeatedly malformed tool calls (default on)."""
    return os.getenv("TITAN_MALFORMED_GUARD", "1").strip().lower() in (
        "1", "true", "yes"
    )


def malformed_guard_limit() -> int:
    """How many malformed calls of one tool are tolerated before blocking."""
    try:
        return max(1, int(os.getenv("TITAN_MALFORMED_GUARD_LIMIT", "2")))
    except (TypeError, ValueError):
        return 2


# ---- Phase 34: tool-result size cap ------------------------------------------
# A single oversized tool output (a 500KB log dump, a whole-file read) can
# flood the model's context window. Tool results appended to the conversation
# are capped at `TITAN_TOOL_RESULT_MAX_CHARS` with an explicit truncation
# marker, so the model still knows the output was cut and how large it was.
def tool_result_max_chars() -> int:
    """Maximum characters of a tool result kept in the conversation."""
    try:
        return max(256, int(os.getenv("TITAN_TOOL_RESULT_MAX_CHARS", "4000")))
    except (TypeError, ValueError):
        return 4000


# ---- Phase 37: dead-end early stop ------------------------------------------
# When EVERY tool call in a batch fails (error return, malformed skip, or a
# guard block) with no successful result at all, the run is probably grinding
# on a broken path. After `TITAN_DEAD_END_WINDOW` (default 5) consecutive
# all-failed tool batches the harness stops early with an explicit notice
# instead of burning the remaining steps and token budget. 0 disables it.
def dead_end_window() -> int:
    """Consecutive all-failed tool batches tolerated before an early stop."""
    try:
        return max(0, int(os.getenv("TITAN_DEAD_END_WINDOW", "5")))
    except (TypeError, ValueError):
        return 5


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
