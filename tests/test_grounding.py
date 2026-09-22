"""Phase 20 tests: grounded final validation — a final answer produced without
ANY tool use gets exactly one forced verification pass before finalizing
(anti-hallucination for weak local models), and tool-using runs never pay
for it. All deterministic: fake LLM + fake tool executor, no network."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.agent import TitanAgent
from titan_agent.llm_client import LLMResponse
from titan_agent.memory import MemoryManager


class _QueuedLLM:
    """Returns scripted responses from a queue, then 'done' forever."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def chat_completion(self, messages, tools=None, **kw):
        self.calls += 1
        if not self.responses:
            return LLMResponse(content="done")
        return self.responses.pop(0)


def _tool_call(name="read_file", args='{"path": "x"}'):
    return {"id": "call_g", "function": {"name": name, "arguments": args}}


class _FakeExec:
    """Pretends to run tools; records what was executed."""

    def __init__(self):
        self.executed = []

    async def __call__(self, name, args):
        self.executed.append((name, args))
        return "GROUNDED-EVIDENCE"


def _grounding_on(monkeypatch):
    monkeypatch.setenv("TITAN_FINAL_GROUNDING", "1")


async def _collect(agent, session="g"):
    out = [
        ev
        async for ev in agent.run_task(
            "task", session_id=session, mode="fast", strategy="auto"
        )
    ]
    finals = [ev.data for ev in out if ev.type == "final_answer"]
    return (finals[0] if finals else None), out


async def _run(llm, tmp_path, session="g", fake_exec=None):
    agent = TitanAgent(
        llm=llm,
        memory=MemoryManager(tmp_path / "g.db"),
        core_memory_path=tmp_path / "g_core.db",
    )
    if fake_exec is not None:
        agent.execute_tool_unified = fake_exec
    final, out = await _collect(agent, session)
    return final, out


def _statuses(events):
    return [str(ev.data) for ev in events if ev.type == "status"]


def test_zero_tool_answer_gets_grounding_pass(tmp_path, monkeypatch):
    """Draft with no tools -> grounding turn emits a tool call -> it executes
    -> the loop continues and the (grounded) final is produced."""
    _grounding_on(monkeypatch)
    fake_exec = _FakeExec()
    llm = _QueuedLLM([
        LLMResponse(content="draft without tools"),                  # call 1
        LLMResponse(content="", tool_calls=[_tool_call()]),          # call 2 grounding
        LLMResponse(content="GROUNDED final"),                       # call 3
        LLMResponse(content="GROUNDED final"),                       # call 4 reflection
    ])

    final, events = asyncio.run(
        _run(llm, tmp_path, session="g1", fake_exec=fake_exec)
    )
    assert final == "GROUNDED final"
    assert fake_exec.executed == [("read_file", {"path": "x"})]
    statuses = _statuses(events)
    assert any("Verifying answer" in s for s in statuses)
    assert llm.calls == 4


def test_conceptual_answer_declines_tools_and_finalizes(tmp_path, monkeypatch):
    """A pure-chat answer can explicitly decline tools; the final is its
    reply and grounding runs exactly once (no infinite loop)."""
    _grounding_on(monkeypatch)
    llm = _QueuedLLM([
        LLMResponse(content="Hello! How can I help?"),               # call 1
        LLMResponse(content="NO_TOOLS_NEEDED - this is a greeting."),  # call 2
    ])

    final, events = asyncio.run(_run(llm, tmp_path, session="g3"))
    assert final == "NO_TOOLS_NEEDED - this is a greeting."
    assert llm.calls == 2
    statuses = _statuses(events)
    assert sum("Verifying answer" in s for s in statuses) == 1


def test_grounding_error_keeps_draft_answer(tmp_path, monkeypatch):
    """If the grounding call itself fails, we degrade to the draft instead of
    crashing the run (Claude-Code-style graceful degradation)."""
    _grounding_on(monkeypatch)

    class _BoomLLM(_QueuedLLM):
        async def chat_completion(self, messages, tools=None, **kw):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(content="draft answer")
            raise RuntimeError("provider down")

    llm = _BoomLLM([])
    final, events = asyncio.run(_run(llm, tmp_path, session="g4"))
    assert final == "draft answer"
    assert any(ev.type == "error" for ev in events)
    assert llm.calls == 2


def test_tool_using_run_never_grounds(tmp_path, monkeypatch):
    """Runs that already used tools skip the grounding pass entirely."""
    _grounding_on(monkeypatch)
    fake_exec = _FakeExec()
    llm = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),          # call 1 tool use
        LLMResponse(content="final from tools"),                     # call 2
        LLMResponse(content="final from tools"),                     # call 3 reflection
    ])

    final, events = asyncio.run(
        _run(llm, tmp_path, session="g6", fake_exec=fake_exec)
    )
    assert fake_exec.executed                       # the tool ran
    assert final == "final from tools"
    assert not any("Verifying answer" in s for s in _statuses(events))


def test_zero_tool_grounding_can_be_disabled(tmp_path, monkeypatch):
    """TITAN_FINAL_GROUNDING=0 restores the old fast path: the draft finalizes
    with exactly one model call and no verification status."""
    monkeypatch.setenv("TITAN_FINAL_GROUNDING", "0")
    llm = _QueuedLLM([LLMResponse(content="plain answer")])

    final, events = asyncio.run(_run(llm, tmp_path, session="g5"))
    assert final == "plain answer"
    assert llm.calls == 1
    assert not any("Verifying answer" in s for s in _statuses(events))