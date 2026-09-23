"""Tests for Free API Key Providers & Models Catalog."""
import pytest
from titan_agent.free_providers import get_free_providers, get_provider_by_id
from titan_agent.commands import LOCAL_COMMANDS, parse_local


def test_free_providers_catalog_structure():
    providers = get_free_providers()
    assert len(providers) >= 8

    provider_ids = {p["id"] for p in providers}
    assert "openrouter" in provider_ids
    assert "groq" in provider_ids
    assert "gemini" in provider_ids
    assert "sambanova" in provider_ids
    assert "github" in provider_ids
    assert "mistral" in provider_ids
    assert "puter" in provider_ids
    assert "g4f" in provider_ids

    for p in providers:
        assert "name" in p
        assert "portal_url" in p
        assert "models" in p
        assert len(p["models"]) > 0
        for m in p["models"]:
            assert "id" in m
            assert "name" in m


def test_get_provider_by_id():
    gemini = get_provider_by_id("gemini")
    assert gemini is not None
    assert "Gemini" in gemini["name"]
    assert "aistudio.google.com" in gemini["portal_url"]

    groq = get_provider_by_id("groq")
    assert groq is not None
    assert "console.groq.com" in groq["portal_url"]


def test_free_models_slash_command():
    assert "free-models" in LOCAL_COMMANDS
    parsed = parse_local("/free-models")
    assert parsed is not None
    assert parsed["name"] == "free-models"
