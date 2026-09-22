"""Phase 19 tests: the live HITL approvals panel is wired into the web UI."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

WEB_UI = Path(__file__).resolve().parent.parent / "titan_agent" / "web_ui"


def _read(name):
    return (WEB_UI / name).read_text(encoding="utf-8")


def test_index_has_approvals_panel():
    html = _read("index.html")
    assert 'id="hitl-requests"' in html
    assert "Approvals" in html
    assert 'id="hitl-count"' in html
    assert "fetchHITLPending" in html


def test_app_js_wires_hitl_endpoints_and_polling():
    js = _read("app.js")
    assert "fetchHITLPending" in js
    assert "decideHITL" in js
    assert "/api/hitl/pending" in js
    assert "/api/hitl/decide" in js
    assert "request_id" in js
    assert "'approve'" in js
    assert "'deny'" in js
    # Auto-refresh every 5s with a pause-on-failure guard
    assert "setInterval" in js
    assert "5000" in js
    assert "60000" in js


def test_app_js_reuses_escape_helper():
    js = _read("app.js")
    # Panel rendering escapes dynamic fields before injecting innerHTML
    assert "escapeHtml(req.action)" in js
    assert "escapeHtml(req.reason)" in js