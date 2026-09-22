"""Phase 29 tests: repeated-failure guard observability API.

`GET /api/guard/state` exposes the live agent's per-run guard counters
(identical tool calls that keep failing) plus the effective config, so an
operator can see what the harness is blocking. Auth-protected like every /api
route. Deterministic: seeded counter dict on the live agent, no network.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

_TEST_KEY = "sk-test-" + uuid.uuid4().hex
os.environ.setdefault("TITAN_API_KEY", _TEST_KEY)

import titan_agent.server as server_mod


@pytest.fixture()
def client() -> TestClient:
    yield TestClient(server_mod.app)
    # Restore a clean guard state on the live global agent after each test.
    server_mod.agent._guard_failures = {}
    server_mod.agent._malformed_calls = {}


def test_guard_state_requires_auth(client: TestClient) -> None:
    anon = client.get("/api/guard/state")
    assert anon.status_code in (401, 403)


def test_guard_state_returns_config_and_empty_counters(client: TestClient) -> None:
    server_mod.agent._guard_failures = {}
    server_mod.agent._malformed_calls = {}
    resp = client.get("/api/guard/state", headers={
        "Authorization": f"Bearer {os.environ.get('TITAN_API_KEY', _TEST_KEY)}"
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["limit"] == 2
    assert body["blocked_patterns"] == []
    # Phase 35: malformed-arguments guard section mirrored.
    assert body["malformed"]["enabled"] is True
    assert body["malformed"]["limit"] == 2
    assert body["malformed"]["patterns"] == []


def test_guard_state_lists_blocked_patterns(client: TestClient) -> None:
    server_mod.agent._guard_failures = {
        "web_fetch\x00{}": 2,
        "read_file\x00{}": 1,
        "grep\x00{}": 5,
    }
    resp = client.get("/api/guard/state", headers={
        "Authorization": f"Bearer {os.environ.get('TITAN_API_KEY', _TEST_KEY)}"
    })
    assert resp.status_code == 200
    patterns = resp.json()["blocked_patterns"]
    # sorted worst-first, tool field extracted from the composite key
    assert patterns[0] == {"tool": "grep", "failures": 5}
    assert [p["tool"] for p in patterns] == ["grep", "web_fetch", "read_file"]


def test_guard_state_lists_malformed_patterns(client: TestClient) -> None:
    """Phase 35: skipped malformed calls per tool name surface too."""
    server_mod.agent._guard_failures = {}
    server_mod.agent._malformed_calls = {
        "write_file": 2,
        "web_fetch": 7,
    }
    resp = client.get("/api/guard/state", headers={
        "Authorization": f"Bearer {os.environ.get('TITAN_API_KEY', _TEST_KEY)}"
    })
    assert resp.status_code == 200
    patterns = resp.json()["malformed"]["patterns"]
    assert [p["tool"] for p in patterns] == ["web_fetch", "write_file"]
    assert patterns[0] == {"tool": "web_fetch", "skipped": 7}