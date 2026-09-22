"""Phase 13 — Provider fallback chain tests.

``TITAN_PROVIDER_FALLBACK_CHAIN`` lets ``LLMClient.chat_completion`` roll over
to sibling providers when the primary fails with a TRANSIENT error (network,
timeout, HTTP 408/429/5xx, unconfigured). Auth (401/403) and malformed-request
errors fail fast by design. All tests are deterministic and network-free: the
per-provider HTTP call is scripted, and the chain comes from call-time env.
"""
import asyncio
from typing import Any

import aiohttp
import pytest

import titan_agent.llm_client as llm_client_mod
from titan_agent.llm_client import LLMClient, LLMResponse


def run_async(coro):
    """Run one async coroutine to completion (deterministic, no event pollution)."""
    return asyncio.run(coro)


def make_script(client: LLMClient, outcomes: list[Any]) -> "_ScriptedOnce":
    """Install a scripted ``_chat_completion_once`` onto the client instance.

    The fake is an instance attribute, so ``client._chat_completion_once(...)``
    calls it directly (no self binding) and it can snapshot the live
    provider/model per attempt.
    """

    class Scripted(_ScriptedOnce):
        async def __call__(self, messages, tools=None, temperature=0.6, max_tokens=4096):
            self.calls.append((client.provider, client.model))
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    script = Scripted(outcomes)
    client._chat_completion_once = script  # type: ignore[method-assign]
    return script


class _ScriptedOnce:
    """Replacement for ``_chat_completion_once`` with a queue of outcomes.

    Each entry is either an ``LLMResponse`` (returned) or an ``Exception``
    (raised). Records the client's provider/model exactly when called, so tests
    can assert which provider actually served (or failed) each attempt.
    """

    def __init__(self, outcomes: list[Any]):
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, str]] = []


# ---------------------------------------------------------------------------
# Chain construction
# ---------------------------------------------------------------------------

def test_fallback_chain_priority_order_and_dedup(monkeypatch):
    """Primary first, then chain entries in order; duplicates removed."""
    monkeypatch.setenv("TITAN_PROVIDER_FALLBACK_CHAIN", "groq,kimi,groq")
    monkeypatch.setattr(llm_client_mod, "GROQ_API_KEY", "sk-groq")
    monkeypatch.setattr(llm_client_mod, "KIMI_API_KEY", "sk-kimi")
    client = LLMClient(provider="openrouter", model="hermes-3")
    chain = client._build_fallback_chain()
    assert chain == [
        ("openrouter", "hermes-3"),
        ("groq", "llama-3.3-70b-versatile"),
        ("kimi", "kimi-k3"),
    ]


def test_fallback_chain_skips_provider_without_key(monkeypatch):
    """A chain entry that needs a key but has none is skipped entirely."""
    monkeypatch.setenv("TITAN_PROVIDER_FALLBACK_CHAIN", "deepseek,groq")
    monkeypatch.setattr(llm_client_mod, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(llm_client_mod, "GROQ_API_KEY", "sk-groq")
    client = LLMClient(provider="openrouter", model="hermes-3")
    chain = client._build_fallback_chain()
    assert ("deepseek", "deepseek-chat") not in chain
    assert ("groq", "llama-3.3-70b-versatile") in chain


def test_fallback_chain_includes_local_without_key(monkeypatch):
    """Local providers (ollama/lmstudio) never need a key to join the chain."""
    monkeypatch.setenv("TITAN_PROVIDER_FALLBACK_CHAIN", "ollama")
    client = LLMClient(provider="openrouter", model="hermes-3")
    chain = client._build_fallback_chain()
    assert ("ollama", "hermes3:8b") in chain


def test_fallback_chain_model_overrides(monkeypatch):
    """TITAN_PROVIDER_FALLBACK_MODELS overrides the default model per provider."""
    monkeypatch.setenv("TITAN_PROVIDER_FALLBACK_CHAIN", "groq")
    monkeypatch.setenv("TITAN_PROVIDER_FALLBACK_MODELS", "groq=custom-groq-model")
    monkeypatch.setattr(llm_client_mod, "GROQ_API_KEY", "sk-groq")
    client = LLMClient(provider="openrouter", model="hermes-3")
    chain = client._build_fallback_chain()
    assert ("groq", "custom-groq-model") in chain


def test_build_fallback_chain_empty_env_primary_only(monkeypatch):
    """With no chain env, only the primary provider is attempted."""
    monkeypatch.setenv("TITAN_PROVIDER_FALLBACK_CHAIN", "")
    client = LLMClient(provider="openrouter", model="hermes-3")
    assert client._build_fallback_chain() == [("openrouter", "hermes-3")]


# ---------------------------------------------------------------------------
# Fallback behaviour at call time
# ---------------------------------------------------------------------------

def test_primary_success_no_fallback(monkeypatch):
    """A healthy primary means the chain is never consulted."""
    monkeypatch.setenv("TITAN_PROVIDER_FALLBACK_CHAIN", "groq")
    monkeypatch.setattr(llm_client_mod, "GROQ_API_KEY", "sk-groq")
    client = LLMClient(provider="openrouter", model="hermes-3")
    script = make_script(client, [LLMResponse(content="primary ok")])

    res = run_async(client.chat_completion([{"role": "user", "content": "hi"}]))

    assert res.content == "primary ok"
    assert [(p, m) for p, m in script.calls] == [("openrouter", "hermes-3")]


def test_fallback_on_network_error(monkeypatch):
    """Network errors roll to the next provider; result/metadata restored."""
    monkeypatch.setenv("TITAN_PROVIDER_FALLBACK_CHAIN", "groq")
    monkeypatch.setattr(llm_client_mod, "GROQ_API_KEY", "sk-groq")
    client = LLMClient(provider="openrouter", model="hermes-3")
    script = make_script(
        client,
        [aiohttp.ClientError("connection refused"), LLMResponse(content="groq ok")],
    )

    res = run_async(client.chat_completion([{"role": "user", "content": "hi"}]))

    assert res.content == "groq ok"
    assert [p for p, _ in script.calls] == ["openrouter", "groq"]
    # The client's configured provider/model are restored after the fallback.
    assert client.provider == "openrouter"
    assert client.model == "hermes-3"


def test_fallback_on_rate_limit_429(monkeypatch):
    """HTTP 429 is transient → the next provider is tried."""
    monkeypatch.setenv("TITAN_PROVIDER_FALLBACK_CHAIN", "groq")
    monkeypatch.setattr(llm_client_mod, "GROQ_API_KEY", "sk-groq")
    client = LLMClient(provider="openrouter", model="hermes-3")
    script = make_script(
        client,
        [
            RuntimeError("LLM API Error [429] from openrouter (hermes-3): rate limited"),
            LLMResponse(content="groq ok"),
        ],
    )

    res = run_async(client.chat_completion([{"role": "user", "content": "hi"}]))

    assert res.content == "groq ok"
    assert [p for p, _ in script.calls] == ["openrouter", "groq"]


def test_fallback_on_server_error_500(monkeypatch):
    """HTTP 5xx is transient → falls back to the sibling provider."""
    monkeypatch.setenv("TITAN_PROVIDER_FALLBACK_CHAIN", "ollama")
    client = LLMClient(provider="openrouter", model="hermes-3")
    script = make_script(
        client,
        [
            RuntimeError("LLM API Error [503] from openrouter (hermes-3): overloaded"),
            LLMResponse(content="local ok"),
        ],
    )

    res = run_async(client.chat_completion([{"role": "user", "content": "hi"}]))

    assert res.content == "local ok"
    assert [p for p, _ in script.calls] == ["openrouter", "ollama"]


def test_auth_error_fails_fast_401(monkeypatch):
    """401 is NOT transient — it propagates without trying the chain."""
    monkeypatch.setenv("TITAN_PROVIDER_FALLBACK_CHAIN", "groq")
    monkeypatch.setattr(llm_client_mod, "GROQ_API_KEY", "sk-groq")
    client = LLMClient(provider="openrouter", model="hermes-3")
    script = make_script(
        client,
        [RuntimeError("LLM API Error [401] from openrouter (hermes-3): bad key")],
    )

    with pytest.raises(RuntimeError, match=r"\[401\]"):
        run_async(client.chat_completion([{"role": "user", "content": "hi"}]))

    # Only ONE attempt — the chain was never consulted.
    assert len(script.calls) == 1


def test_all_providers_fail_aggregates_errors(monkeypatch):
    """When every provider fails, the aggregate error names all details."""
    monkeypatch.setenv("TITAN_PROVIDER_FALLBACK_CHAIN", "groq,ollama")
    monkeypatch.setattr(llm_client_mod, "GROQ_API_KEY", "sk-groq")
    client = LLMClient(provider="openrouter", model="hermes-3")
    script = make_script(
        client,
        [
            RuntimeError("LLM API Error [429] from openrouter (hermes-3): one"),
            RuntimeError("LLM API Error [503] from groq (llama): two"),
            aiohttp.ClientError("offline"),
        ],
    )

    with pytest.raises(RuntimeError, match=r"All providers failed"):
        run_async(client.chat_completion([{"role": "user", "content": "hi"}]))

    assert len(script.calls) == 3
    # Config restored even on total failure.
    assert client.provider == "openrouter"
    assert client.model == "hermes-3"


def test_unconfigured_primary_falls_back(monkeypatch):
    """A primary with no endpoint can still roll to a configured sibling."""
    monkeypatch.setenv("TITAN_PROVIDER_FALLBACK_CHAIN", "ollama")
    client = LLMClient(provider="openrouter", model="hermes-3")
    client.base_url = ""  # simulate a stripped-down configuration
    script = make_script(
        client,
        [
            RuntimeError("Provider 'openrouter' is not configured (missing API key)."),
            LLMResponse(content="local ok"),
        ],
    )

    res = run_async(client.chat_completion([{"role": "user", "content": "hi"}]))

    assert res.content == "local ok"
    assert [p for p, _ in script.calls] == ["openrouter", "ollama"]


# ---------------------------------------------------------------------------
# Eligibility classifier unit tests
# ---------------------------------------------------------------------------

def test_transient_classifier():
    assert LLMClient._is_transient_api_error(RuntimeError("LLM API Error [429] x"))
    assert LLMClient._is_transient_api_error(RuntimeError("LLM API Error [503] x"))
    assert LLMClient._is_transient_api_error(RuntimeError("LLM API Error [500] x"))
    assert LLMClient._is_transient_api_error(RuntimeError("LLM API Error [408] x"))
    assert LLMClient._is_transient_api_error(
        RuntimeError("Provider 'x' is not configured (missing API key).")
    )


def test_non_transient_classifier():
    assert not LLMClient._is_transient_api_error(RuntimeError("LLM API Error [401] x"))
    assert not LLMClient._is_transient_api_error(RuntimeError("LLM API Error [403] x"))
    assert not LLMClient._is_transient_api_error(RuntimeError("LLM API Error [400] x"))
    assert not LLMClient._is_transient_api_error(RuntimeError("LLM API Error [404] x"))
    assert not LLMClient._is_transient_api_error(RuntimeError("boom"))


# ---------------------------------------------------------------------------
# Credential availability
# ---------------------------------------------------------------------------

def test_has_credentials(monkeypatch):
    monkeypatch.setattr(llm_client_mod, "GROQ_API_KEY", "sk-groq")
    monkeypatch.setattr(llm_client_mod, "DEEPSEEK_API_KEY", "")
    assert LLMClient._has_credentials("groq")
    assert not LLMClient._has_credentials("deepseek")
    assert LLMClient._has_credentials("ollama")  # local: no key needed
    assert LLMClient._has_credentials("lmstudio")
    assert not LLMClient._has_credentials("unknown-provider")