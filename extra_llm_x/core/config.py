"""Extra LLM X — System Configuration & Environment Settings.

Manages network bindings, provider endpoints, auto-discovery parameters,
and SQLite database locations for API key storage.
"""
import os
import socket
from pathlib import Path
from dotenv import load_dotenv

# Base directories
PACKAGE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PACKAGE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables: check extra_llm_x/.env, then parent .env
if (PACKAGE_DIR / ".env").exists():
    load_dotenv(PACKAGE_DIR / ".env")
elif (PACKAGE_DIR.parent / ".env").exists():
    load_dotenv(PACKAGE_DIR.parent / ".env")
else:
    load_dotenv()

# Network Settings
HOST = os.getenv("ELX_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.getenv("ELX_PORT", "21000"))

def find_available_port(host: str, start_port: int, max_attempts: int = 100) -> int:
    """Find the next available TCP port if start_port is occupied."""
    bind_host = "127.0.0.1" if host in ("0.0.0.0", "localhost") else host
    for p in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((bind_host, p))
                return p
            except OSError:
                continue
    return start_port

PORT = find_available_port(HOST, DEFAULT_PORT)

# Storage & Database
DB_PATH = DATA_DIR / "elx.db"

# Master Administration Secret (if empty, generates one or allows local access)
ADMIN_SECRET = os.getenv("ELX_ADMIN_SECRET", "")

# 100% Free Providers API Keys (Optional, zero-key models work without keys!)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")

# Local Endpoints
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")

# Remote Provider Base URLs
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
SAMBANOVA_BASE_URL = os.getenv("SAMBANOVA_BASE_URL", "https://api.sambanova.ai/v1")
GITHUB_MODELS_BASE_URL = os.getenv("GITHUB_MODELS_BASE_URL", "https://models.inference.ai.azure.com")
MISTRAL_BASE_URL = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
HUGGINGFACE_BASE_URL = os.getenv("HUGGINGFACE_BASE_URL", "https://api-inference.huggingface.co/v1")

# Virtual Model Aliases
VIRTUAL_MODELS = {
    "auto": "Routes to the fastest, healthiest available free model across all providers.",
    "auto/free": "Direct alias for auto.",
    "auto/coding": "Routes to the highest-performing free programming & code generation model.",
    "auto/fast": "Routes to the lowest latency ultra-fast free model (e.g. Groq LPU).",
    "auto/reasoning": "Routes to deep chain-of-thought free reasoning models (e.g. DeepSeek R1).",
    "auto/vision": "Routes to free multimodal vision models (e.g. Gemini 2.0 Flash).",
    "auto/offline": "Routes to local offline models (Ollama / LM Studio) with zero internet traffic.",
}
