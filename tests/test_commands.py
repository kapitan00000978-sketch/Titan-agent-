"""Slash command tests (Block 4: Hermes-class command layer)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.commands import ALL_COMMANDS, COMMANDS, expand_slash, parse_local


def test_expand_slash_plans_deep_high():
    result = expand_slash("/plan build a search feature")
    assert result is not None
    assert result["command"] == "plan"
    assert result["mode"] == "deep"
    assert result["effort"] == "high"
    assert "build a search feature" in result["prompt"]
    assert "TASK" in result["prompt"]


def test_expand_slash_review_and_security():
    r = expand_slash("/review tools.py")
    assert r["mode"] == "deep" and r["effort"] == "high"
    assert "tools.py" in r["prompt"]
    s = expand_slash("/security-scan backend/")
    assert s["mode"] == "deep" and s["effort"] == "ultra"
    assert "backend/" in s["prompt"]


def test_expand_slash_research_sets_deep_search():
    r = expand_slash("/research quantum batteries")
    assert r["mode"] == "deep_search"
    assert "quantum batteries" in r["prompt"]


def test_expand_slash_no_arg_still_works():
    r = expand_slash("/plan")
    assert r is not None
    assert "general case" in r["prompt"] or "arg" in r["prompt"]


def test_expand_slash_returns_none_for_normal_input():
    assert expand_slash("hello world") is None
    assert expand_slash("") is None
    assert expand_slash("/") is None
    assert expand_slash("/unknowncmd foo") is None
    assert expand_slash("/help") is None  # local command, not an LLM command


def test_parse_local_commands():
    assert parse_local("/help")["name"] == "help"
    assert parse_local("/status")["name"] == "status"
    assert parse_local("/memory apple juice")["arg"] == "apple juice"
    assert parse_local("/mode deep")["name"] == "mode"
    assert parse_local("/unknown") is None
    assert parse_local("not a command") is None


def test_command_catalog_is_english_and_has_hermes_core():
    names = set(ALL_COMMANDS.keys())
    for needed in ("plan", "review", "security-scan", "research", "help", "status", "skills", "handoffs"):
        assert needed in names, f"missing command: {needed}"
    assert not any("ü" in v.lower() for v in ALL_COMMANDS.values())  # English UI text


def test_every_llm_command_has_valid_mode_effort():
    valid_modes = ("fast", "deep", "deep_search")
    valid_efforts = ("auto", "low", "medium", "high", "ultra")
    for name, cmd in COMMANDS.items():
        assert cmd["mode"] in valid_modes, name
        assert cmd["effort"] in valid_efforts, name
        assert "{arg}" in cmd["template"], name