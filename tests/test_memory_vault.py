"""Memory Vault scope + handoff tests (Block 3: Hermes Memory Vault pattern)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.memory import MemoryManager, VALID_SCOPES


def test_vault_scoped_write_and_search(tmp_path):
    mem = MemoryManager(tmp_path / "test_vault.db")
    mem.vault_remember("project", "tech_stack", "FastAPI + React", "project")
    mem.vault_remember("project", "owner", "Alisher", "profile")
    mem.vault_remember("user", "coffee", "black, no sugar", "preference")

    scoped = mem.vault_search("FastAPI", scope="project")
    assert len(scoped) == 1
    assert scoped[0]["key"] == "tech_stack"
    assert scoped[0]["scope"] == "project"

    # Same key in different scope must not collide
    mem.vault_remember("team", "owner", "Team Lead", "profile")
    both = mem.vault_list()
    owners = [f for f in both if f["key"] == "owner"]
    assert len(owners) == 2
    assert {f["scope"] for f in owners} == {"project", "team"}


def test_vault_defaults_to_global_scope(tmp_path):
    mem = MemoryManager(tmp_path / "test_vault2.db")
    mem.remember_fact("k1", "v1", scope="global")  # explicit
    result = mem.vault_search("v1")
    assert len(result) == 1
    assert result[0]["scope"] == "global"


def test_remember_fact_without_scope_backwards_compatible(tmp_path):
    """Legacy path (no scope) must still write to the knowledge table."""
    mem = MemoryManager(tmp_path / "test_legacy.db")
    mem.remember_fact("user_name", "Alisher", "profile")
    facts = mem.search_knowledge("Alisher")
    assert len(facts) == 1
    assert facts[0]["key"] == "user_name"


def test_remember_fact_with_scope_routes_to_vault(tmp_path):
    mem = MemoryManager(tmp_path / "test_scoped_route.db")
    mem.remember_fact("api_key_note", "store in secrets", scope="team")
    results = mem.vault_search("store in secrets", scope="team")
    assert len(results) == 1
    assert results[0]["scope"] == "team"


def test_recall_relevant_merges_vault_facts(tmp_path):
    mem = MemoryManager(tmp_path / "test_recall.db")
    mem.remember_fact("city", "Tashkent", "profile")
    mem.vault_remember("user", "favorite_food", "plov", "preference")
    recalled = mem.recall_relevant("I love plov in Tashkent", limit=5)
    keys = {f["key"] for f in recalled}
    assert "favorite_food" in keys
    assert "city" in keys


def test_handoff_lifecycle(tmp_path):
    mem = MemoryManager(tmp_path / "test_handoff.db")
    hid = mem.create_handoff("Continue auth work", "The login flow is WIP; next: add refresh token.", scope="project")
    assert hid > 0
    open_list = mem.list_handoffs(status="open")
    assert len(open_list) == 1
    assert open_list[0]["title"] == "Continue auth work"
    assert mem.resolve_handoff(hid) is True
    assert mem.list_handoffs(status="open") == []
    resolved = mem.list_handoffs(status="resolved")
    assert len(resolved) == 1
    assert mem.resolve_handoff(99999) is False


def test_valid_scopes_constant():
    assert set(VALID_SCOPES) == {"global", "project", "team", "user"}