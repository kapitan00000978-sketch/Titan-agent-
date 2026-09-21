"""Phase 6 — OmniRoute provider integration tests.

OmniRoute is a self-hosted AI gateway (localhost:20128/v1) that exposes smart
auto-routing virtual models: auto, auto/coding, auto/fast, auto/smart,
auto/offline, auto/cheap. The key was verified live against the gateway before
these tests were written.
"""
from __future__ import annotations

from titan_agent import config
from titan_agent.llm_client import LLMClient


def test_config_omni_defaults():
    """OmniRoute base URL / model constants must have sane defaults."""
    assert config.OMNI_BASE_URL == "http://localhost:20128/v1"
    assert config.OMNI_MODEL == "auto"


def test_config_omni_auto_models():
    """All six auto-routing models requested by the user are registered."""
    expected = [
        "auto",
        "auto/coding",
        "auto/fast",
        "auto/smart",
        "auto/offline",
        "auto/cheap",
    ]
    assert list(config.OMNI_AUTO_MODELS) == expected
    for m in expected:
        assert m in config.OMNI_AUTO_MODELS


def test_llm_client_omni_provider_credentials():
    """LLMClient(provider='omni') must point at the gateway with the set key."""
    client = LLMClient(provider="omni", model="auto")
    assert client.base_url == config.OMNI_BASE_URL
    assert client.api_key == config.OMNI_API_KEY
    assert client.model == "auto"


def test_llm_client_omni_set_model():
    """set_model('omni', ...) re-resolves the gateway credentials."""
    client = LLMClient()
    client.set_model("omni", "auto")
    assert client.provider == "omni"
    assert client.base_url == config.OMNI_BASE_URL
    assert client.api_key == config.OMNI_API_KEY


def test_config_v2_omni_fields():
    """Pydantic settings layer exposes OmniRoute fields."""
    from titan_agent.config_v2 import LLMSettings

    s = LLMSettings()
    assert s.omni_base_url == "http://localhost:20128/v1"
    assert s.omni_model == "auto"