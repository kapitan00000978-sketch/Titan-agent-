from pathlib import Path
from titan_agent.core.memory.working_memory_virtualizer import (
    WorkingMemoryVirtualizer,
    WorkingMemoryState,
)


def test_working_memory_basic_operations():
    mem = WorkingMemoryVirtualizer("Build a secure web server")
    assert mem.state.goal == "Build a secure web server"

    mem.set_subtask("Configure TLS certificates")
    assert mem.state.active_subtask == "Configure TLS certificates"

    mem.confirm_fact("OpenSSL 3.0 installed")
    mem.confirm_fact("Port 443 available")
    # Duplicate should not be added
    mem.confirm_fact("Port 443 available")
    assert len(mem.state.confirmed_facts) == 2

    mem.record_dead_end("Avoid python http.server without TLS")
    assert len(mem.state.refuted_dead_ends) == 1

    mem.pin_path("cert_file", "/etc/ssl/cert.pem")
    assert mem.state.pinned_paths["cert_file"] == "/etc/ssl/cert.pem"

    mem.add_todo("Generate DH parameters")
    assert "Generate DH parameters" in mem.state.pending_todos
    assert mem.complete_todo("Generate DH parameters") is True
    assert "Generate DH parameters" not in mem.state.pending_todos


def test_working_memory_auto_observe_tool_outcome():
    mem = WorkingMemoryVirtualizer("Optimize database")

    # Successful read
    mem.auto_observe_tool_outcome(
        tool_name="read_file",
        tool_args={"path": "server.py"},
        tool_result="import socket\n# content",
    )
    assert any("server.py" in f for f in mem.state.confirmed_facts)
    assert "server.py" in mem.state.pinned_paths

    # Tool error
    mem.auto_observe_tool_outcome(
        tool_name="execute_command",
        tool_args={"command": "systemctl restart nginx"},
        tool_result="Error: systemctl command not found on host",
    )
    assert any("Avoid execute_command" in d for d in mem.state.refuted_dead_ends)


def test_working_memory_hud_rendering():
    mem = WorkingMemoryVirtualizer("Fix memory leak")
    mem.set_subtask("Profile heap allocations")
    mem.confirm_fact("Heap growth is in cache dictionary")
    mem.record_dead_end("Do not use unbounded lru_cache")
    mem.pin_path("cache_module", "core/cache.py")
    mem.add_todo("Apply LRU expiration policy")

    hud = mem.render_hud_block(max_chars=600)
    assert "### WORKING MEMORY HUD" in hud
    assert "Goal**: Fix memory leak" in hud
    assert "Active Subtask**: Profile heap allocations" in hud
    assert "Heap growth is in cache dictionary" in hud
    assert "Do not use unbounded lru_cache" in hud
    assert "core/cache.py" in hud
    assert "Apply LRU expiration policy" in hud


def test_working_memory_state_serialization():
    original = WorkingMemoryState(
        goal="Test goal",
        active_subtask="Subtask 1",
        confirmed_facts=["F1", "F2"],
        refuted_dead_ends=["D1"],
        pinned_paths={"main": "main.py"},
        pending_todos=["T1"],
    )
    d = original.to_dict()
    restored = WorkingMemoryState.from_dict(d)
    assert restored.goal == original.goal
    assert restored.confirmed_facts == original.confirmed_facts
    assert restored.refuted_dead_ends == original.refuted_dead_ends
    assert restored.pinned_paths == original.pinned_paths
