"""Catalog of Free API Key Providers & Keyless Models.

Provides comprehensive metadata, direct registration links, and recommended
free models across top AI platforms offering free tier API keys or keyless inference.
"""
from typing import Any, Dict, List

FREE_PROVIDERS: List[Dict[str, Any]] = [
    {
        "id": "extra-llm-x",
        "name": "Extra LLM X (640+ Free Models Unified Gateway)",
        "portal_url": "http://localhost:3000",
        "base_url": "http://localhost:3000/v1",
        "env_var": "EXTRA_LLM_X_API_KEY",
        "no_key_required": True,
        "free_tier_info": "Self-hosted gateway aggregating 26 free providers, smart combos, and local key generation.",
        "models": [
            {"id": "extra/auto-free", "name": "Extra Auto-Free (Smart Router)", "desc": "Fastest available healthy free model across 26 providers"},
            {"id": "extra/free-coding", "name": "Extra Free Coding", "desc": "Qwen 2.5 Coder 32B / Codestral / DeepSeek Coder"},
            {"id": "extra/free-fast", "name": "Extra Free Fast (LPU/Wafer)", "desc": "Cerebras 2,000 tok/s & Groq 500 tok/s sub-second inference"},
            {"id": "extra/free-reasoning", "name": "Extra Free Reasoning", "desc": "DeepSeek R1 / Gemini 2.0 Flash Thinking"},
            {"id": "extra/free-vision", "name": "Extra Free Vision", "desc": "Multimodal vision & image comprehension"},
        ],
    },
    {
        "id": "openrouter",
        "name": "OpenRouter (20+ Free Models)",
        "portal_url": "https://openrouter.ai/keys",
        "base_url": "https://openrouter.ai/api/v1",
        "env_var": "OPENROUTER_API_KEY",
        "no_key_required": False,
        "free_tier_info": "Free registration, 20+ models completely free with :free tag.",
        "models": [
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "LLaMA 3.3 70B (Free)", "desc": "Frontier open-weights reasoning"},
            {"id": "deepseek/deepseek-r1:free", "name": "DeepSeek R1 (Free)", "desc": "Advanced reasoning & logic"},
            {"id": "google/gemini-2.0-flash-exp:free", "name": "Gemini 2.0 Flash (Free)", "desc": "Ultra-fast multimodal Google model"},
            {"id": "qwen/qwen-2.5-coder-32b-instruct:free", "name": "Qwen 2.5 Coder 32B (Free)", "desc": "Superb coding model"},
            {"id": "mistralai/mistral-7b-instruct:free", "name": "Mistral 7B (Free)", "desc": "Fast & lightweight generalist"},
        ],
    },
    {
        "id": "groq",
        "name": "Groq Cloud (Ultra-Fast LPU)",
        "portal_url": "https://console.groq.com/keys",
        "base_url": "https://api.groq.com/openai/v1",
        "env_var": "GROQ_API_KEY",
        "no_key_required": False,
        "free_tier_info": "Instant free API key, 30 req/min, 500+ tokens/sec inference.",
        "models": [
            {"id": "llama-3.3-70b-versatile", "name": "LLaMA 3.3 70B Versatile", "desc": "Top quality LLaMA model on LPU"},
            {"id": "llama-3.1-8b-instant", "name": "LLaMA 3.1 8B Instant", "desc": "Blazing fast ~800 tokens/sec"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B (32k context)", "desc": "Large context MoE model"},
            {"id": "gemma2-9b-it", "name": "Gemma 2 9B", "desc": "Google Gemma on Groq speed"},
        ],
    },
    {
        "id": "gemini",
        "name": "Google AI Studio (Gemini Free Tier)",
        "portal_url": "https://aistudio.google.com/app/apikey",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "env_var": "GEMINI_API_KEY",
        "no_key_required": False,
        "free_tier_info": "Free forever (no credit card needed): 15 req/min, 1,500 req/day.",
        "models": [
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "desc": "Next-gen ultra fast flagship"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "desc": "1M token context window"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "desc": "Complex multimodal reasoning"},
        ],
    },
    {
        "id": "sambanova",
        "name": "SambaNova Cloud (Free Fast AI)",
        "portal_url": "https://cloud.sambanova.ai/apis",
        "base_url": "https://api.sambanova.ai/v1",
        "env_var": "SAMBANOVA_API_KEY",
        "no_key_required": False,
        "free_tier_info": "100% free developer tier on SN40L chips, no credit card.",
        "models": [
            {"id": "Meta-Llama-3.3-70B-Instruct", "name": "LLaMA 3.3 70B Instruct", "desc": "Full 70B parameter model"},
            {"id": "Qwen2.5-Coder-32B-Instruct", "name": "Qwen 2.5 Coder 32B", "desc": "High accuracy programming"},
            {"id": "Meta-Llama-3.1-8B-Instruct", "name": "LLaMA 3.1 8B Instruct", "desc": "Fast low-latency inference"},
        ],
    },
    {
        "id": "github",
        "name": "GitHub Models (Free with GitHub Token)",
        "portal_url": "https://github.com/settings/tokens",
        "base_url": "https://models.inference.ai.azure.com",
        "env_var": "GITHUB_TOKEN",
        "no_key_required": False,
        "free_tier_info": "Free personal access token (classic or fine-grained), up to 150 req/day.",
        "models": [
            {"id": "gpt-4o", "name": "OpenAI GPT-4o (via GitHub)", "desc": "Flagship GPT-4o via Azure/GitHub"},
            {"id": "gpt-4o-mini", "name": "OpenAI GPT-4o Mini", "desc": "Fast economical GPT-4o"},
            {"id": "Phi-4", "name": "Microsoft Phi-4", "desc": "14B state-of-the-art reasoning"},
            {"id": "Meta-Llama-3.1-70B-Instruct", "name": "LLaMA 3.1 70B", "desc": "Azure-hosted Meta LLaMA"},
        ],
    },
    {
        "id": "mistral",
        "name": "Mistral AI (Codestral Free Tier)",
        "portal_url": "https://console.mistral.ai/api-keys/",
        "base_url": "https://api.mistral.ai/v1",
        "env_var": "MISTRAL_API_KEY",
        "no_key_required": False,
        "free_tier_info": "Free developer tier for Codestral code generation model.",
        "models": [
            {"id": "codestral-latest", "name": "Codestral Latest", "desc": "Specialized code generation brain"},
            {"id": "mistral-small-latest", "name": "Mistral Small Latest", "desc": "Efficient generalist model"},
        ],
    },
    {
        "id": "huggingface",
        "name": "Hugging Face Serverless Inference",
        "portal_url": "https://huggingface.co/settings/tokens",
        "base_url": "https://api-inference.huggingface.co/v1",
        "env_var": "HUGGINGFACE_API_KEY",
        "no_key_required": False,
        "free_tier_info": "Free user access token for thousands of open models.",
        "models": [
            {"id": "meta-llama/Llama-3.2-3B-Instruct", "name": "LLaMA 3.2 3B Instruct", "desc": "Lightweight & responsive"},
            {"id": "Qwen/Qwen2.5-Coder-32B-Instruct", "name": "Qwen 2.5 Coder 32B", "desc": "Open coding benchmark leader"},
        ],
    },
    {
        "id": "puter",
        "name": "Puter.js (100% Free & Zero-Key In-Browser)",
        "portal_url": "https://developer.puter.com",
        "base_url": "",
        "env_var": "",
        "no_key_required": True,
        "free_tier_info": "500+ models completely free with zero setup directly in the browser.",
        "models": [
            {"id": "deepseek/deepseek-v4-pro", "name": "DeepSeek V4 Pro", "desc": "Full 671B reasoning"},
            {"id": "claude-3-5-sonnet", "name": "Claude 3.5 Sonnet", "desc": "State-of-the-art coding and prose"},
            {"id": "gpt-4o", "name": "GPT-4o", "desc": "Omni multimodal model"},
        ],
    },
    {
        "id": "g4f",
        "name": "GPT4Free (100% Free & Zero-Key)",
        "portal_url": "https://github.com/xtekky/gpt4free",
        "base_url": "",
        "env_var": "",
        "no_key_required": True,
        "free_tier_info": "Built-in free web gateway with zero API keys required.",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o (g4f)", "desc": "Zero-key access to GPT-4o"},
            {"id": "gpt-4", "name": "GPT-4 (g4f)", "desc": "Reliable fallback"},
        ],
    },
    {
        "id": "ollama",
        "name": "Ollama (100% Offline Local Models)",
        "portal_url": "https://ollama.com",
        "base_url": "http://localhost:11434/v1",
        "env_var": "",
        "no_key_required": True,
        "free_tier_info": "Completely private, air-gapped, zero cost, runs on your hardware.",
        "models": [
            {"id": "hermes3:8b", "name": "Hermes 3 (8B)", "desc": "Native tool-use specialist"},
            {"id": "qwen2.5-coder:7b", "name": "Qwen 2.5 Coder (7B)", "desc": "Efficient local coding brain"},
            {"id": "deepseek-r1:8b", "name": "DeepSeek R1 Distill (8B)", "desc": "Local chain-of-thought"},
        ],
    },
]


def get_free_providers() -> List[Dict[str, Any]]:
    """Return all catalogued free API providers."""
    return FREE_PROVIDERS


def get_provider_by_id(provider_id: str) -> Dict[str, Any] | None:
    """Find a provider definition by ID."""
    p_id = provider_id.lower().strip()
    for p in FREE_PROVIDERS:
        if p["id"].lower() == p_id:
            return p
    return None
