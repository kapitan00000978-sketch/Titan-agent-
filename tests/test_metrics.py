"""Unit tests for Prometheus metrics exporter endpoint."""
import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.server import app


def test_metrics_endpoints_public_and_formatted():
    client = TestClient(app)

    # Test /metrics
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    text = res.text
    assert "# HELP titan_tool_calls_total" in text
    assert "# HELP titan_skills_total" in text
    assert "titan_skills_total" in text
    assert "titan_system_info{status=\"ready\"} 1" in text

    # Test /api/metrics
    res2 = client.get("/api/metrics")
    assert res2.status_code == 200
    assert "titan_skills_total" in res2.text
