"""Phase 22 tests: per-tool telemetry + adaptive tool record.

Every tool call funnels through ``TitanAgent.execute_tool_unified``, which
records success/failure/latency/output size without changing any behavior.
Tests cover: the success-path record, the error-path record, the exception
re-raise record, the ``tool_stats`` introspection tool, catalog wiring, the
opt-in TOOL RECORD prompt injection (and its absence by default), the bounded
prompt block math, and the auth-protected ``GET /api/tools/stats`` route.
Deterministic: isolated collectors, real local memory tools, no network.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from titan_agent.agent import TitanAgent
from titan_agent.llm_client import LLMResponse
from titan_agent.memory import MemoryManager
from titan_agent.tool_stats import TOOL_STATS, ToolStatsCollector


class _FakeLLM:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = 0
        self.systems = []

    async def chat_completion(self, messages, tools=None, **kw):
        self.calls += 1
        self.systems.append(messages[0]["content"] if messages else "")
        if not self.responses:
            return LLMResponse(content="done")
        return self.responses.pop(0)


def _agent(tmp_path, llm=None, **kw):
    return TitanAgent(
        llm=llm or _FakeLLM(),
        memory=MemoryManager(tmp_path / "t.db"),
        core_memory_path=tmp_path / "t_core.db",
        **kw,
    )


# ---------------------------------------------------------------------------
# Recording through the real executor
# ---------------------------------------------------------------------------


def test_execute_records_success_and_error(tmp_path):
    stats = ToolStatsCollector()
    agent = _agent(tmp_path, tool_stats=stats)

    ok = asyncio.run(agent.execute_tool_unified("memory_save",
                                                {"key": "k1", "value": "v1"}))
    assert ok.startswith("Saved to memory")
    err = asyncio.run(agent.execute_tool_unified("no_such_tool", {}))
    assert err.startswith("Error")

    s = stats.summary()
    assert s["totals"] == {"calls": 2, "ok": 1, "errors": 1}
    mem = s["tools"]["memory_save"]
    assert mem["calls"] == 1 and mem["ok"] == 1 and mem["errors"] == 0
    bad = s["tools"]["no_such_tool"]
    assert bad["calls"] == 1 and bad["errors"] == 1 and bad["error_rate"] == 1.0
    assert bad["last_error"] == "tool_error"


def test_execute_records_exception_and_reraises(tmp_path):
    stats = ToolStatsCollector()
    agent = _agent(tmp_path, tool_stats=stats)

    async def boom(name, args):
        raise PermissionError("nope")

    agent._execute_tool_unified = boom
    raised = False
    try:
        asyncio.run(agent.execute_tool_unified("read_file", {"path": "x"}))
    except PermissionError:
        raised = True
    assert raised, "the original exception must still propagate"
    s = stats.summary()
    assert s["totals"]["errors"] == 1
    assert s["tools"]["read_file"]["last_error"] == "PermissionError"


# ---------------------------------------------------------------------------
# tool_stats introspection tool
# ---------------------------------------------------------------------------


def test_tool_stats_tool_returns_summary(tmp_path):
    stats = ToolStatsCollector()
    stats.record("read_file", ok=False, latency_ms=10, error="FileNotFoundError")
    stats.record("read_file", ok=True, latency_ms=5, output_chars=120)
    agent = _agent(tmp_path, tool_stats=stats)
    out = asyncio.run(agent.execute_tool_unified("tool_stats", {}))
    data = json.loads(out)
    assert data["totals"] == {"calls": 2, "ok": 1, "errors": 1}
    rf = data["tools"]["read_file"]
    assert rf["error_rate"] == 0.5
    assert rf["avg_latency_ms"] == 7.5
    assert rf["avg_output_chars"] == 60.0
    assert rf["last_error"] == "FileNotFoundError"


def test_tool_stats_appears_in_catalog(tmp_path):
    agent = _agent(tmp_path)
    names = [t["function"]["name"] for t in agent._build_tools_list()]
    assert "tool_stats" in names
    assert "tool_stats" in agent._build_tool_catalog_text()


# ---------------------------------------------------------------------------
# Sums, bounds and the adaptive prompt block
# ---------------------------------------------------------------------------


def test_summary_math():
    stats = ToolStatsCollector()
    stats.record("a", ok=True, latency_ms=10, output_chars=100)
    stats.record("a", ok=False, latency_ms=20, error="E1")
    stats.record("a", ok=False, latency_ms=30, error="E2")
    s = stats.summary()
    assert s["totals"] == {"calls": 3, "ok": 1, "errors": 2}
    a = s["tools"]["a"]
    assert a["error_rate"] == round(2 / 3, 3)
    assert a["avg_latency_ms"] == round(60 / 3, 1)
    assert a["avg_output_chars"] == round(100 / 3, 1)
    assert a["last_error"] == "E2"


def test_prompt_block_empty_for_healthy_tools():
    stats = ToolStatsCollector()
    for _ in range(3):
        stats.record("read_file", ok=True, latency_ms=5, output_chars=10)
    assert stats.prompt_block() == ""
    # failures below the min_calls threshold are not surfaced either
    stats.record("grep", ok=False, latency_ms=5, error="x")
    stats.record("grep", ok=False, latency_ms=5, error="x")
    assert stats.prompt_block() == ""


def test_prompt_block_surfaces_repeat_failures():
    stats = ToolStatsCollector()
    for _ in range(4):
        stats.record("web_fetch", ok=False, latency_ms=800, error="TimeoutError")
    stats.record("read_file", ok=True, latency_ms=5, output_chars=10)
    block = stats.prompt_block()
    assert "### TOOL RECORD" in block
    assert "web_fetch" in block
    assert "4 failed" in block
    assert "100%" in block
    assert "read_file" not in block  # healthy tools are never surfaced


# ---------------------------------------------------------------------------
# Prompt injection is opt-in via TITAN_TOOL_RECORD
# ---------------------------------------------------------------------------


async def _run_with_system_capture(tmp_path, monkeypatch, stats, session):
    llm = _FakeLLM([LLMResponse(content="FINAL")])
    agent = _agent(tmp_path, llm=llm, tool_stats=stats)
    finals = [
        ev.data
        async for ev in agent.run_task(
            "task", session_id=session, mode="fast", strategy="auto"
        )
        if ev.type == "final_answer"
    ]
    assert finals == ["FINAL"]
    return llm


def test_tool_record_injected_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_TOOL_RECORD", "1")
    monkeypatch.setenv("TITAN_FINAL_GROUNDING", "0")
    stats = ToolStatsCollector()
    for _ in range(3):
        stats.record("web_fetch", ok=False, latency_ms=800, error="TimeoutError")
    llm = asyncio.run(_run_with_system_capture(tmp_path, monkeypatch, stats, "s-inj"))
    assert "### TOOL RECORD" in llm.systems[0]
    assert "web_fetch" in llm.systems[0]


def test_tool_record_absent_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_TOOL_RECORD", "0")
    monkeypatch.setenv("TITAN_FINAL_GROUNDING", "0")
    stats = ToolStatsCollector()
    for _ in range(5):
        stats.record("web_fetch", ok=False, latency_ms=10, error="Err")
    llm = asyncio.run(_run_with_system_capture(tmp_path, monkeypatch, stats, "s-def"))
    assert "### TOOL RECORD" not in llm.systems[0]
    assert "web_fetch" not in llm.systems[0]


# ---------------------------------------------------------------------------
# Server endpoint (auth-protected like every /api route)
# ---------------------------------------------------------------------------

_TEST_KEY = "sk-test-" + uuid.uuid4().hex
os.environ.setdefault("TITAN_API_KEY", _TEST_KEY)

from titan_agent.server import app  # (after env setup)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_tools_stats_endpoint(client: TestClient) -> None:
    TOOL_STATS.clear()
    TOOL_STATS.record("read_file", ok=True, latency_ms=5, output_chars=10)

    # 401 without a token (route is auto-guarded by _apply_auth_dependency)
    anon = client.get("/api/tools/stats")
    assert anon.status_code in (401, 403)

    resp = client.get("/api/tools/stats", headers={
        "Authorization": f"Bearer {os.environ.get('TITAN_API_KEY', _TEST_KEY)}"
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["totals"] == {"calls": 1, "ok": 1, "errors": 0}
    assert body["tools"]["read_file"]["avg_latency_ms"] == 5.0
    TOOL_STATS.clear()