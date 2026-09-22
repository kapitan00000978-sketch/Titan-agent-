"""Phase 18 tests: context compaction — LLM-condensing of trimmed regions
instead of dropping them silently (Claude-Code-style compact)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.agent import (
    CONTEXT_TRIM_MARKER,
    TitanAgent,
    compact_messages_for_context,
    trim_messages_for_context,
)
from titan_agent.llm_client import LLMResponse
from titan_agent.memory import MemoryManager


def _tool_block(prefix, n, content_len=200):
    msgs = []
    for k in range(n):
        msgs.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": f"call_{prefix}_{k}",
                "function": {"name": "run_command",
                             "arguments": '{"command": "echo"}'},
            }],
        })
        msgs.append({
            "role": "tool",
            "tool_call_id": f"call_{prefix}_{k}",
            "name": "run_command",
            "content": "x" * content_len,
        })
    return msgs


def _big_messages():
    return ([{"role": "system", "content": "SYS"},
             {"role": "user", "content": "task"}]
            + _tool_block("a", 30, content_len=300))


def test_compaction_none_summarizer_equals_legacy_trim():
    msgs = _big_messages()
    compacted = asyncio.run(
        compact_messages_for_context(msgs, summarizer=None, max_chars=1000)
    )
    plain = trim_messages_for_context(msgs, max_chars=1000)
    assert compacted == plain
    assert any(CONTEXT_TRIM_MARKER in str(m.get("content") or "") for m in compacted)


def test_compaction_replaces_marker_with_summary():
    msgs = _big_messages()
    origin_len = len(msgs)
    calls = []

    async def fake_summarizer(dropped):
        calls.append(len(dropped))
        return "SUMMARY-OF-EARLIER-WORK"

    out = asyncio.run(
        compact_messages_for_context(msgs, summarizer=fake_summarizer, max_chars=1000)
    )

    # dropped = real messages removed (the summary block replaced the marker)
    assert calls == [origin_len - (len(out) - 1)]
    assert not any(
        CONTEXT_TRIM_MARKER in str(m.get("content") or "") for m in out
    )
    blocks = [m for m in out if m.get("role") == "system"
              and "Background" in str(m.get("content") or "")]
    assert len(blocks) == 1
    assert "SUMMARY-OF-EARLIER-WORK" in blocks[0]["content"]
    assert len(out) < len(msgs)


def test_compaction_under_budget_never_calls_summarizer():
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}]
    calls = []

    async def fake_summarizer(dropped):
        calls.append(1)
        return "nope"

    out = asyncio.run(
        compact_messages_for_context(msgs, summarizer=fake_summarizer, max_chars=100_000)
    )
    assert calls == []
    assert out == msgs


def test_compaction_summarizer_failure_falls_back_to_marker():
    msgs = _big_messages()

    async def bad_summarizer(dropped):
        raise RuntimeError("summarizer down")

    out = asyncio.run(
        compact_messages_for_context(msgs, summarizer=bad_summarizer, max_chars=1000)
    )
    assert any(CONTEXT_TRIM_MARKER in str(m.get("content") or "") for m in out)


def test_compaction_empty_summary_falls_back_to_marker():
    msgs = _big_messages()

    async def empty_summarizer(dropped):
        return "   "

    out = asyncio.run(
        compact_messages_for_context(msgs, summarizer=empty_summarizer, max_chars=1000)
    )
    assert any(CONTEXT_TRIM_MARKER in str(m.get("content") or "") for m in out)


# --------------------------------------------------------------------------
# Agent-level wiring: _summarize_context + overflow path
# --------------------------------------------------------------------------

class _FakeLLM:
    def __init__(self, content="S-OK", error=None):
        self.content = content
        self.error = error
        self.prompts = []

    async def chat_completion(self, messages, tools=None, **kw):
        self.prompts.append(messages)
        if self.error:
            raise self.error
        return LLMResponse(content=self.content)


def _agent_with_llm(tmp_path, fake):
    return TitanAgent(
        llm=fake,
        memory=MemoryManager(tmp_path / "cp.db"),
        core_memory_path=tmp_path / "cp_core.db",
    )


def test_agent_summarize_context_returns_text(tmp_path):
    fake = _FakeLLM(content=" KEPT-INFO ")
    agent = _agent_with_llm(tmp_path, fake)
    dropped = [
        {"role": "tool", "content": "file-a-result"},
        {"role": "assistant", "content": "created X"},
    ]
    out = asyncio.run(agent._summarize_context(dropped))
    assert out == "KEPT-INFO"
    # The dropped content is actually fed into the summarizer prompt
    assert "created X" in fake.prompts[0][0]["content"]


def test_agent_summarize_context_failure_returns_none(tmp_path):
    fake = _FakeLLM(error=RuntimeError("boom"))
    agent = _agent_with_llm(tmp_path, fake)
    out = asyncio.run(agent._summarize_context([{"role": "tool", "content": "res"}]))
    assert out is None


def test_chat_with_recovery_compacts_on_overflow(tmp_path, monkeypatch):
    # A provider window smaller than our heuristic budget triggers a trim +
    # summarizer round; the run must still finish with the summary in place.
    monkeypatch.setattr("titan_agent.agent.CONTEXT_BUDGET_CHARS", 200_000)
    summaries = []

    class _OverflowLLM:
        def __init__(self):
            self.calls = 0

        async def chat_completion(self, messages, tools=None, **kw):
            self.calls += 1
            payload = sum(len(str(m.get("content") or "")) for m in messages)
            if payload > 5_000:
                raise RuntimeError(
                    "Error code: 400 - maximum context length exceeded "
                    "(this model can only handle a tiny window)"
                )
            return LLMResponse(content="done")

    fake = _OverflowLLM()
    agent = _agent_with_llm(tmp_path, fake)

    async def _hook(dropped):
        summaries.append(len(dropped))
        return "COMPACTED-BG"

    agent._summarize_context = _hook  # deterministic: no nested LLM call

    big = ([{"role": "system", "content": "SYS"},
            {"role": "user", "content": "task"}]
           + _tool_block("h", 40, content_len=200))

    resp, working, notes = asyncio.run(agent._chat_with_recovery(big, []))

    assert resp.content == "done"
    assert summaries  # the compaction summarizer actually ran
    assert any("Background" in str(m.get("content") or "") for m in working)
    assert any("Context overflow" in n for n in notes)