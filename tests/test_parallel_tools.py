"""Phase 17 tests: bounded, crash-isolated, optionally cancel-on-failure
parallel tool execution inside a single model turn."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.agent import TitanAgent
from titan_agent.memory import MemoryManager


class _Resp:
    def __init__(self, calls, content=""):
        self.tool_calls = calls
        self.content = content
        self.thoughts = ""


def _call(i, name="run_command", args='{"command": "echo ok"}'):
    return {"id": f"call_{i}", "function": {"name": name, "arguments": args}}


class _ExecFake:
    """Records a concurrency watermark and simulates failures / hangs."""

    def __init__(self, fail_on=(), block_forever=(), delay=0.01):
        self.fail_on = set(fail_on)
        self.block_forever = set(block_forever)
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self.executed = []

    async def __call__(self, name, args):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if name in self.fail_on:
                raise KeyError(f"boom-{name}")
            if name in self.block_forever:
                # Only exits via task cancellation (never completes normally)
                await asyncio.Event().wait()
            if self.delay:
                await asyncio.sleep(self.delay)
            self.executed.append(name)
            return f"ok-{name}"
        finally:
            self.active -= 1


def _make_agent(tmp_path, exec_fake):
    agent = TitanAgent(
        llm=None,  # _emit_tool_results never calls the LLM
        memory=MemoryManager(tmp_path / "par.db"),
        core_memory_path=tmp_path / "par_core.db",
    )
    agent.execute_tool_unified = exec_fake  # type: ignore[method-assign]
    return agent


async def _emit(agent, resp):
    messages = []
    events = []
    async for ev in agent._emit_tool_results(resp, messages, 1):
        events.append(ev)
    return events, messages


def test_parallel_bounded_by_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_PARALLEL_TOOL_CALLS", "2")
    monkeypatch.delenv("TITAN_CANCEL_ON_TOOL_ERROR", raising=False)
    exec_fake = _ExecFake(delay=0.02)
    agent = _make_agent(tmp_path, exec_fake)
    resp = _Resp([_call(i) for i in range(5)])

    asyncio.run(_emit(agent, resp))

    # Concurrency never exceeds the cap even with 5 calls
    assert exec_fake.max_active <= 2
    assert exec_fake.max_active == 2
    # and every call still completed
    assert len(exec_fake.executed) == 5


def test_serial_mode_runs_one_at_a_time(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_PARALLEL_TOOL_CALLS", "1")
    monkeypatch.delenv("TITAN_CANCEL_ON_TOOL_ERROR", raising=False)
    exec_fake = _ExecFake(delay=0.01)
    agent = _make_agent(tmp_path, exec_fake)
    resp = _Resp([_call(i) for i in range(4)])

    asyncio.run(_emit(agent, resp))

    assert exec_fake.max_active == 1
    assert len(exec_fake.executed) == 4


def test_crash_isolation_keeps_siblings_running(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_PARALLEL_TOOL_CALLS", "4")
    monkeypatch.delenv("TITAN_CANCEL_ON_TOOL_ERROR", raising=False)
    exec_fake = _ExecFake(fail_on={"tool_boom"}, delay=0.005)
    agent = _make_agent(tmp_path, exec_fake)
    resp = _Resp([_call(0, "tool_boom"), _call(1), _call(2)])

    _events, messages = asyncio.run(_emit(agent, resp))

    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    by_id = {m["tool_call_id"]: m["content"] for m in tool_msgs}
    # The crashing tool reports its error as an ordinary tool result...
    assert "Error (KeyError)" in by_id["call_0"]
    assert "boom-tool_boom" in by_id["call_0"]
    # ...while its siblings still ran and answered
    assert by_id["call_1"] == "ok-run_command"
    assert by_id["call_2"] == "ok-run_command"
    assert len(exec_fake.executed) == 2
    # Every tool_call_id receives exactly one follow-up message (API pairing)
    assert [m["tool_call_id"] for m in tool_msgs] == ["call_0", "call_1", "call_2"]


def test_cancel_on_tool_error_cancels_siblings(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_PARALLEL_TOOL_CALLS", "4")
    monkeypatch.setenv("TITAN_CANCEL_ON_TOOL_ERROR", "1")
    exec_fake = _ExecFake(
        fail_on={"tool_fast_fail"}, block_forever={"tool_hang"}
    )
    agent = _make_agent(tmp_path, exec_fake)
    resp = _Resp([
        _call(0, "tool_fast_fail"),
        _call(1, "tool_hang"),
        _call(2, "tool_hang"),
    ])

    events, messages = asyncio.run(_emit(agent, resp))

    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    by_id = {m["tool_call_id"]: m["content"] for m in tool_msgs}
    assert "KeyError" in by_id["call_0"]
    assert "cancelled" in by_id["call_1"]
    assert "cancelled" in by_id["call_2"]
    # Hung tools were cancelled, never completed
    assert exec_fake.executed == []
    statuses = [str(ev.data) for ev in events if ev.type == "status"]
    assert any("Cancelled" in s for s in statuses)


def test_default_mode_reports_all_results_after_one_failure(tmp_path, monkeypatch):
    # Without the cancel flag, a failure never prunes a sibling's result —
    # the model sees every outcome, success or error, in the same turn.
    monkeypatch.setenv("TITAN_PARALLEL_TOOL_CALLS", "4")
    monkeypatch.delenv("TITAN_CANCEL_ON_TOOL_ERROR", raising=False)
    exec_fake = _ExecFake(fail_on={"tool_boom"}, delay=0.005)
    agent = _make_agent(tmp_path, exec_fake)
    resp = _Resp([_call(0, "tool_boom"), _call(1)])

    _events, messages = asyncio.run(_emit(agent, resp))

    by_id = {m["tool_call_id"]: m["content"] for m in messages if m.get("role") == "tool"}
    assert "Error (KeyError)" in by_id["call_0"]
    assert by_id["call_1"] == "ok-run_command"