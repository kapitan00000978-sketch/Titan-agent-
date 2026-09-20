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

# If an API key is present, default to that provider; otherwise seamlessly use local Ollama!
if OPENROUTER_API_KEY:
    DEFAULT_PROVIDER = os.getenv("TITAN_PROVIDER", "openrouter")
    DEFAULT_MODEL = os.getenv("TITAN_MODEL", "nousresearch/hermes-3-llama-3.1-405b:free")
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
