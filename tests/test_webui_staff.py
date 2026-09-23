"""Tests for the Subagent Staff Roster Web UI and /api/staff/roles endpoint."""
import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.server import app
from titan_agent.auth import get_server_api_key

WEB_UI = Path(__file__).resolve().parent.parent / "titan_agent" / "web_ui"


def _read(name):
    return (WEB_UI / name).read_text(encoding="utf-8")


def _auth_headers():
    key = get_server_api_key()
    return {"Authorization": f"Bearer {key}"} if key else {}


def test_index_has_subagents_panel():
    html = _read("index.html")
    assert 'id="subagents-list"' in html
    assert "Subagent Roster" in html
    assert 'id="staff-count"' in html
    assert "fetchStaffRoles" in html


def test_app_js_wires_staff_endpoint():
    js = _read("app.js")
    assert "fetchStaffRoles" in js
    assert "/api/staff/roles" in js
    assert "selectStaffRole" in js
    assert "subagent-card" in js


def test_api_staff_roles_endpoint():
    client = TestClient(app)
    res = client.get("/api/staff/roles", headers=_auth_headers())
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["roles"]) >= 16
    role_ids = [r["id"] for r in data["roles"]]
    assert "security" in role_ids
    assert "test_writer" in role_ids
    assert "planner" in role_ids
    assert "coder" in role_ids
