"""Phase 10 hardening tests: context budget trimming, tool-arguments repair,
transient LLM recovery, and context-overflow halving + retry."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aiohttp

from titan_agent.agent import (
    TitanAgent,
    parse_tool_arguments,
    trim_messages_for_context,
)
from titan_agent.llm_client import LLMResponse
from titan_agent.memory import MemoryManager

# --------------------------------------------------------------------------
# trim_messages_for_context
# --------------------------------------------------------------------------

def _tool_block(prefix: str, n: int) -> list[dict]:
    msgs = []
    for k in range(n):
        msgs.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": f"call_{prefix}_{k}",
                "function": {"name": "run_command", "arguments": '{"command": "echo"}'},
            }],
        })
        msgs.append({
            "role": "tool",
            "tool_call_id": f"call_{prefix}_{k}",
            "name": "run_command",
            "content": f"result-{prefix}-{k}-" + "x" * 200,
        })
    return msgs


def test_trim_noop_under_budget():
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "task"}] + _tool_block("a", 3)
    out = trim_messages_for_context(msgs, max_chars=10_000)
    assert out == msgs


def test_trim_keeps_head_and_newest_tail():
    head = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "task-do-this"}]
    msgs = head + _tool_block("b", 12)
    out = trim_messages_for_context(msgs, max_chars=2000)
    # Head survived, in order
    assert out[0] == head[0]
    assert {"role": "user", "content": "task-do-this"} in out
    # The newest tool round survived in FULL (atomic block)
    assert any(m.get("content", "").startswith("result-b-11-") for m in out)
    # Oldest rounds were dropped
    assert len(out) < len(msgs)
    assert not any(m.get("content", "").startswith("result-b-0-") for m in out)
    # Marker present so the model knows context was truncated
    assert any("context trimmed" in str(m.get("content") or "") for m in out)
    # Total (content only) stays inside budget plus marker slack
    total = sum(len(str(m.get("content") or "")) for m in out)
    assert total <= 2000 + 60


def test_trim_preserves_tool_block_atomicity():
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "t"}] + _tool_block("z", 20)
    out = trim_messages_for_context(msgs, max_chars=1500)
    for i, m in enumerate(out):
        if m.get("role") == "assistant" and m.get("tool_calls"):
            ids = {tc.get("id") for tc in m["tool_calls"]}
            j = i + 1
            followed = []
            while j < len(out) and out[j].get("role") == "tool":
                followed.append(out[j].get("tool_call_id"))
                j += 1
            assert set(followed) == ids, f"incomplete tool block at index {i}"


def test_trim_never_keeps_orphan_tool_messages():
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "t"}] + _tool_block("q", 8)
    out = trim_messages_for_context(msgs, max_chars=800)
    has_assistant = any(m.get("role") == "assistant" for m in out)
    has_tool = any(m.get("role") == "tool" for m in out)
    # Either a whole block survived, or none of it did — no lone tool messages.
    assert not has_tool or has_assistant


# --------------------------------------------------------------------------
# parse_tool_arguments
# --------------------------------------------------------------------------

def test_parse_tool_arguments_valid_payloads():
    assert parse_tool_arguments(None) == {}
    assert parse_tool_arguments("") == {}
    assert parse_tool_arguments("   ") == {}
    assert parse_tool_arguments({"a": 1}) == {"a": 1}
    assert parse_tool_arguments('{"a": 1}') == {"a": 1}
    assert parse_tool_arguments('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_tool_arguments('```\n{"a": 1}\n```') == {"a": 1}
    assert parse_tool_arguments('`{"a": 1}`') == {"a": 1}
    assert parse_tool_arguments('garbage {"a": [1, 2]} tail') == {"a": [1, 2]}


def test_parse_tool_arguments_non_dict_and_invalid():
    # Bare JSON scalars get wrapped so the tool can still be invoked sensibly
    assert parse_tool_arguments('"hello"') == {"value": "hello"}
    assert parse_tool_arguments("[1, 2]") == {"value": [1, 2]}
    # Truly unparsable payloads return None (caller skips + reports)
    assert parse_tool_arguments("not json at all") is None
    assert parse_tool_arguments("{broken") is None


# --------------------------------------------------------------------------
# _emit_tool_results: skip unparsable calls, keep API pairing valid
# --------------------------------------------------------------------------

class _Resp:
    def __init__(self, calls, content=""):
        self.tool_calls = calls
        self.content = content
        self.thoughts = ""


def _make_agent(tmp_path, llm=None):
    mem = MemoryManager(tmp_path / "harden.db")
    return TitanAgent(
        llm=llm or _ScriptedLLM(),
        memory=mem,
        core_memory_path=tmp_path / "harden_core.db",
    )


def test_emit_skips_unparsable_call_with_feedback(tmp_path):
    agent = _make_agent(tmp_path)
    resp = _Resp([
        {"id": "call_1", "function": {"name": "run_command", "arguments": "this is not json at all"}},
    ])
    messages = []

    async def _collect():
        events = []
        async for ev in agent._emit_tool_results(resp, messages, 1):
            events.append(ev)
        return events

    events = asyncio.run(_collect())
    tool_res = [ev.data for ev in events if ev.type == "tool_result"]
    assert len(tool_res) == 1
    assert "could not be parsed" in str(tool_res[0]["result"])
    # assistant->tool pairing stays valid for the next model request
    assert messages[-1]["role"] == "tool"
    assert "could not be parsed" in messages[-1]["content"]


class _RecordingAgent(TitanAgent):
    """Agent whose tool execution is recorded, never runs real tools."""

    def __init__(self, tmp_path):
        super().__init__(
            llm=_ScriptedLLM(),
            memory=MemoryManager(tmp_path / "rec.db"),
            core_memory_path=tmp_path / "rec_core.db",
        )
        self.executed = []

    async def execute_tool_unified(self, name: str, args: dict) -> str:
        self.executed.append((name, args))
        return f"{name}:ok"


def test_emit_runs_valid_calls_and_skips_bad_one_in_order(tmp_path):
    agent = _RecordingAgent(tmp_path)
    resp = _Resp([
        {"id": "call_1", "function": {"name": "run_command", "arguments": '{"command": "echo ok"}'}},
        {"id": "call_2", "function": {"name": "run_command", "arguments": "}[bad json{"}},
    ])
    messages = []

    async def _collect():
        events = []
        async for ev in agent._emit_tool_results(resp, messages, 1):
            events.append(ev)
        return events

    events = asyncio.run(_collect())
    results = [ev.data for ev in events if ev.type == "tool_result"]
    assert len(results) == 2
    # Valid call executed, bad one skipped with explicit feedback (original order)
    assert agent.executed == [("run_command", {"command": "echo ok"})]
    assert "could not be parsed" in str(results[1]["result"])
    assert len(messages) == 3  # assistant + 2 tool messages (API pairing intact)


# --------------------------------------------------------------------------
# _chat_with_recovery: transient retry + overflow halving
# --------------------------------------------------------------------------

class _ScriptedLLM:
    """Raises scripted errors / size-based context overflows, then answers."""

    def __init__(self, errors=(), answer="done", overflow_above=None):
        self.errors = list(errors)
        self.answer = answer
        self.overflow_above = overflow_above
        self.calls = 0
        self.payloads = []

    async def chat_completion(self, messages, tools=None, **kw):
        self.calls += 1
        payload = sum(len(str(m.get("content") or "")) for m in messages)
        self.payloads.append(payload)
        if self.overflow_above is not None and payload > self.overflow_above:
            raise RuntimeError(
                "Error code: 400 - maximum context length exceeded "
                "(this model can only handle a tiny window)"
            )
        if self.errors:
            raise self.errors.pop(0)
        return LLMResponse(content=self.answer)


async def _run_to_final(llm, tmp_path, session="hard"):
    agent = TitanAgent(
        llm=llm,
        memory=MemoryManager(tmp_path / "run.db"),
        core_memory_path=tmp_path / "run_core.db",
    )
    out = [
        ev
        async for ev in agent.run_task(
            "check workflow", session_id=session, mode="fast", strategy="auto"
        )
    ]
    finals = [ev.data for ev in out if ev.type == "final_answer"]
    return (finals[0] if finals else None), out


def test_transient_llm_error_is_retried_and_run_succeeds(tmp_path):
    llm = _ScriptedLLM(errors=[aiohttp.ClientError("boom")])
    final, events = asyncio.run(_run_to_final(llm, tmp_path))
    assert final == "done"
    assert llm.calls >= 2
    statuses = [str(ev.data) for ev in events if ev.type == "status"]
    assert any("retrying" in s for s in statuses)


def test_persistent_transient_error_still_fails_cleanly(tmp_path):
    # All retries exhausted -> run dies with an error event, not an exception.
    llm = _ScriptedLLM(errors=[OSError("conn reset"), OSError("conn reset"),
                               aiohttp.ClientError("down")])
    _, events = asyncio.run(_run_to_final(llm, tmp_path))
    assert any(ev.type == "error" for ev in events)
    assert not any(ev.type == "final_answer" for ev in events)


def test_chat_with_recovery_halves_on_repeated_overflow(tmp_path, monkeypatch):
    # Our heuristic budget is huge, but the "provider" window is small — the
    # halving recovery must shrink the payload until the call succeeds.
    monkeypatch.setattr("titan_agent.agent.CONTEXT_BUDGET_CHARS", 200_000)
    llm = _ScriptedLLM(overflow_above=5_000)
    agent = _make_agent(tmp_path, llm=llm)
    big = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "task"}] + _tool_block("h", 40)

    resp, working, notes = asyncio.run(agent._chat_with_recovery(big, []))
    assert resp.content == "done"
    assert len(working) < len(big)
    assert any("Context overflow" in n for n in notes)
    assert llm.calls >= 2
    # Payload shrank monotonically across the retries
    assert llm.payloads[-1] < llm.payloads[0]


def test_run_recovers_from_context_overflow_end_to_end(tmp_path):
    # Seed a FAT conversation so the first model call overflows a small window;
    # the run must recover via trimming and finish normally.
    llm = _ScriptedLLM(overflow_above=30_000)
    agent = TitanAgent(
        llm=llm,
        memory=MemoryManager(tmp_path / "ov.db"),
        core_memory_path=tmp_path / "ov_core.db",
    )
    for k in range(10):
        agent.memory.add_message("ov", "assistant", f"historical-{k}-" + "z" * 10_000)

    async def _run():
        out = [
            ev
            async for ev in agent.run_task(
                "recover me", session_id="ov", mode="fast", strategy="auto"
            )
        ]
        finals = [ev.data for ev in out if ev.type == "final_answer"]
        return (finals[0] if finals else None), out

    final, events = asyncio.run(_run())
    assert final == "done"
    assert llm.calls >= 2
    statuses = [str(ev.data) for ev in events if ev.type == "status"]
    assert any("Context overflow" in s for s in statuses)