import json
import re
import aiohttp
from typing import List, Dict, Any, Optional
from .config import (
    DEFAULT_PROVIDER,
    DEFAULT_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENROUTER_API_KEY,
    GROQ_API_KEY,
    DEEPSEEK_API_KEY,
    OLLAMA_BASE_URL,
)

class LLMResponse:
    def __init__(self, content: str = "", tool_calls: Optional[List[Dict[str, Any]]] = None, thoughts: str = ""):
        self.content = content or ""
        self.tool_calls = tool_calls or []
        self.thoughts = thoughts or ""

    def to_dict(self):
        return {
            "content": self.content,
            "tool_calls": self.tool_calls,
            "thoughts": self.thoughts
        }

class LLMClient:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = provider or DEFAULT_PROVIDER
        self.model = model or DEFAULT_MODEL
        self._setup_credentials()

    def _setup_credentials(self):
        if self.provider == "openrouter":
            self.base_url = "https://openrouter.ai/api/v1"
            self.api_key = OPENROUTER_API_KEY
        elif self.provider == "groq":
            self.base_url = "https://api.groq.com/openai/v1"
            self.api_key = GROQ_API_KEY
        elif self.provider == "deepseek":
            self.base_url = "https://api.deepseek.com/v1"
            self.api_key = DEEPSEEK_API_KEY
        elif self.provider == "ollama":
            self.base_url = f"{OLLAMA_BASE_URL}/v1"
            self.api_key = "ollama"
        elif self.provider == "lmstudio":
            self.base_url = "http://localhost:1234/v1"
            self.api_key = "lm-studio"
        elif self.provider == "puter":
            # Puter.js runs fully client-side in the browser (free DeepSeek etc.).
            self.base_url = ""
            self.api_key = ""
        else:
            self.base_url = OPENAI_BASE_URL
            self.api_key = OPENAI_API_KEY

    def set_model(self, provider: str, model: str, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.provider = provider
        self.model = model
        if api_key:
            self.api_key = api_key
        if base_url:
            self.base_url = base_url
        else:
            self._setup_credentials()

    @staticmethod
    async def detect_local_models() -> Dict[str, List[str]]:
        """Scans Ollama and LM Studio for local models."""
        results = {"ollama": [], "lmstudio": []}
        async with aiohttp.ClientSession() as session:
            # Check Ollama
            try:
                async with session.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results["ollama"] = [m["name"] for m in data.get("models", [])]
            except Exception:
                pass
            # Check LM Studio
            try:
                async with session.get("http://localhost:1234/v1/models", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results["lmstudio"] = [m["id"] for m in data.get("data", [])]
            except Exception:
                pass
        return results

    def _extract_thoughts_and_tools(self, text: str) -> tuple[str, str, List[Dict[str, Any]]]:
        thoughts = ""
        tool_calls = []

        # Extract thoughts <thought>...</thought> or <think>...</think> (DeepSeek R1 format)
        thought_match = re.search(r"<(?:thought|scratchpad|think)>(.*?)</(?:thought|scratchpad|think)>", text, re.DOTALL | re.IGNORECASE)
        if thought_match:
            thoughts = thought_match.group(1).strip()
            text = re.sub(r"<(?:thought|scratchpad|think)>.*?</(?:thought|scratchpad|think)>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()

        # Extract tool calls in Hermes 3 format: <tool_call>{"name": "...", "arguments": {...}}</tool_call>
        tool_matches = re.finditer(r"<tool_call>\s*(.*?)\s*</tool_call>", text, re.DOTALL | re.IGNORECASE)
        for match in tool_matches:
            raw_call = match.group(1).strip()
            try:
                parsed = json.loads(raw_call)
                if "name" in parsed:
                    tool_calls.append({
                        "id": f"call_{len(tool_calls)+1}",
                        "type": "function",
                        "function": {
                            "name": parsed["name"],
                            "arguments": json.dumps(parsed.get("arguments", parsed.get("parameters", {})))
                        }
                    })
            except Exception:
                pass

        text = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        return text, thoughts, tool_calls

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.6,
        max_tokens: int = 4096
    ) -> LLMResponse:
        if self.provider == "puter":
            raise RuntimeError(
                "Puter.js runs only inside the browser (Web UI). "
                "For server-side usage, choose OpenRouter, DeepSeek, Groq, OpenAI or Ollama."
            )
        if not self.base_url:
            raise RuntimeError(f"Provider '{self.provider}' is not configured (missing API key).")
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/titan-agent"
            headers["X-Title"] = "Titan Agent"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                if resp.status != 200:
                    err_body = await resp.text()
                    hint = ""
                    if resp.status in (401, 403):
                        hint = (
                            " (Hint: the API key is invalid or not set. "
                            "Choose Puter.js (no key) or Ollama from the Web UI settings, "
                            "or add the correct API key to the .env file)"
                        )
                    raise RuntimeError(
                        f"LLM API Error [{resp.status}] from {self.provider} ({self.model}): {err_body}{hint}"
                    )

                data = await resp.json()
                choice = data["choices"][0]
                message = choice.get("message", {})
                content = message.get("content") or ""
                native_tool_calls = message.get("tool_calls") or []

                cleaned_content, thoughts, parsed_tools = self._extract_thoughts_and_tools(content)

                all_tool_calls = list(native_tool_calls)
                all_tool_calls.extend(parsed_tools)

                return LLMResponse(
                    content=cleaned_content,
                    tool_calls=all_tool_calls,
                    thoughts=thoughts
                )
