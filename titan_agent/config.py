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

# MCP Config Path
MCP_CONFIG_FILE = BASE_DIR / "mcp_servers.json"

# Web Server Settings
SERVER_HOST = os.getenv("TITAN_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("TITAN_PORT", "7860"))

# Agent Autonomy Settings
AUTONOMOUS_MODE = os.getenv("TITAN_AUTONOMOUS", "true").lower() in ("true", "1", "yes")
MAX_ITERATIONS = int(os.getenv("TITAN_MAX_ITERATIONS", "25"))

# Token throughput guardrail: the agent never exceeds this many tokens/second
# (token bucket). 214,000/s is effectively invisible in production but fully
# enforced for every LLM call (backend providers and the Puter browser path).
TOKEN_RATE_LIMIT_PER_SEC = int(os.getenv("TITAN_TOKEN_RATE_LIMIT", "214000"))

# ---- Telegram account manager (opt-in, consent-gated) ----
# TITAN_TELEGRAM_ENABLED must be 'true' for ANY Telegram tool to work.
# API creds come from https://my.telegram.org -> API development tools.
# Sending is only allowed to targets listed in TITAN_TELEGRAM_SEND_ALLOWLIST
# (comma-separated usernames or ids); empty = read-only.
TITAN_TELEGRAM_ENABLED = os.getenv("TITAN_TELEGRAM_ENABLED", "false").lower() in ("true", "1", "yes")
TITAN_TELEGRAM_API_ID = os.getenv("TITAN_TELEGRAM_API_ID", "")
TITAN_TELEGRAM_API_HASH = os.getenv("TITAN_TELEGRAM_API_HASH", "")
TITAN_TELEGRAM_SEND_ALLOWLIST = os.getenv("TITAN_TELEGRAM_SEND_ALLOWLIST", "")
