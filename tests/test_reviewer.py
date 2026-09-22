"""Phase 21 tests: dedicated reviewer model + bounded refinement.

The critic/reflection pass normally runs on the generator model. When a
separate reviewer is injected (or TITAN_REVIEWER_PROVIDER set), the reflection
uses the reviewer and the generator revises against the critique up to
TITAN_REFINEMENT_ROUNDS times. Both are opt-in — no reviewer means the classic
single-reflection behavior, verified by test 2. Deterministic fake LLMs, no
network."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titan_agent.agent import TitanAgent
from titan_agent.llm_client import LLMClient, LLMResponse
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
    return {"id": "call_r", "function": {"name": name, "arguments": args}}


class _FakeExec:
    def __init__(self):
        self.executed = []

    async def __call__(self, name, args):
        self.executed.append((name, args))
        return "EVIDENCE"


async def _run(llm, tmp_path, session="r", fake_exec=None, reviewer_llm=None):
    agent = TitanAgent(
        llm=llm,
        memory=MemoryManager(tmp_path / "r.db"),
        core_memory_path=tmp_path / "r_core.db",
        reviewer_llm=reviewer_llm,
    )
    if fake_exec is not None:
        agent.execute_tool_unified = fake_exec
    out = [
        ev
        async for ev in agent.run_task(
            "task", session_id=session, mode="fast", strategy="auto"
        )
    ]
    finals = [ev.data for ev in out if ev.type == "final_answer"]
    return (finals[0] if finals else None), out


def _statuses(events):
    return [str(ev.data) for ev in events if ev.type == "status"]


def test_reviewer_critiques_and_generator_revises(tmp_path):
    """With a separate reviewer the reflection runs on it and the generator
    gets one bounded revision round addressed to the critique."""
    fake_exec = _FakeExec()
    gen = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),   # call 1: tool use
        LLMResponse(content="DRAFT-FINAL"),                   # call 2: draft
        LLMResponse(content="FINAL-v2"),                      # call 3: revision
    ])
    rev = _QueuedLLM([LLMResponse(content="REVIEWED-FINAL")])  # the critique

    final, events = asyncio.run(
        _run(gen, tmp_path, session="r1", fake_exec=fake_exec, reviewer_llm=rev)
    )
    assert final == "FINAL-v2"
    assert gen.calls == 3
    assert rev.calls == 1
    assert fake_exec.executed                      # tool ran up front
    statuses = _statuses(events)
    assert any("Refining final answer" in s for s in statuses)


def test_no_reviewer_keeps_single_reflection(tmp_path):
    """Backward compatibility: without a reviewer the reflection uses the
    generator itself and NO refinement round runs (extra call never made)."""
    fake_exec = _FakeExec()
    gen = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),   # call 1: tool use
        LLMResponse(content="STABLE-FINAL"),                  # call 2: draft
        LLMResponse(content="STABLE-FINAL"),                  # call 3: reflection
    ])

    final, events = asyncio.run(_run(gen, tmp_path, session="r2", fake_exec=fake_exec))
    assert final == "STABLE-FINAL"
    assert gen.calls == 3
    assert not any("Refining final answer" in s for s in _statuses(events))


def test_refinement_rounds_zero_skips_revision(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_REFINEMENT_ROUNDS", "0")
    fake_exec = _FakeExec()
    gen = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),
        LLMResponse(content="DRAFT-FINAL"),
    ])
    rev = _QueuedLLM([LLMResponse(content="REVIEWED-FINAL")])

    final, events = asyncio.run(
        _run(gen, tmp_path, session="r3", fake_exec=fake_exec, reviewer_llm=rev)
    )
    assert final == "REVIEWED-FINAL"
    assert rev.calls == 1
    assert gen.calls == 2                    # no revision call
    assert not any("Refining final answer" in s for s in _statuses(events))


def test_refinement_tool_call_handoff(tmp_path):
    """If the revision asks for tools, they execute and the loop continues
    instead of emitting an unverified final."""
    fake_exec = _FakeExec()
    gen = _QueuedLLM([
        LLMResponse(content="", tool_calls=[_tool_call()]),   # call 1: tool use
        LLMResponse(content="DRAFT-FINAL"),                   # call 2: draft
        LLMResponse(content="", tool_calls=[_tool_call("run_command",
                                                      '{"command": "verify"}')]),  # call 3: revision needs tools
        LLMResponse(content="AFTER-REFINE-FINAL"),            # call 4: final
    ])
    rev = _QueuedLLM([LLMResponse(content="REVIEWED-FINAL")])

    final, events = asyncio.run(
        _run(gen, tmp_path, session="r4", fake_exec=fake_exec, reviewer_llm=rev)
    )
    assert final == "AFTER-REFINE-FINAL"
    assert len(fake_exec.executed) == 2                      # both tool rounds ran
    assert any("Refining final answer" in s for s in _statuses(events))


def test_refinement_error_keeps_reviewed_final(tmp_path):
    """A failing revision degrades gracefully: the reviewer's final survives."""

    class _BoomRevise(_QueuedLLM):
        async def chat_completion(self, messages, tools=None, **kw):
            self.calls += 1
            if self.calls <= 2:
                return LLMResponse(content="DRAFT-FINAL" if self.calls == 2 else
                                   "", tool_calls=[_tool_call()] if self.calls == 1 else None)
            raise RuntimeError("provider down")

    fake_exec = _FakeExec()
    gen = _BoomRevise([])
    rev = _QueuedLLM([LLMResponse(content="REVIEWED-FINAL")])

    final, events = asyncio.run(
        _run(gen, tmp_path, session="r5", fake_exec=fake_exec, reviewer_llm=rev)
    )
    assert final == "REVIEWED-FINAL"
    assert gen.calls == 3                    # tool, draft, failed revision
    assert any(ev.type == "error" for ev in events)


def test_reviewer_env_autobuild(tmp_path, monkeypatch):
    """TITAN_REVIEWER_PROVIDER builds the reviewer lazily from config and the
    agent's own model is untouched."""
    monkeypatch.setenv("TITAN_REVIEWER_PROVIDER", "kimi")
    monkeypatch.delenv("TITAN_REVIEWER_MODEL", raising=False)
    gen = _QueuedLLM([LLMResponse(content="ok")])
    agent = TitanAgent(
        llm=gen,
        memory=MemoryManager(tmp_path / "r6.db"),
        core_memory_path=tmp_path / "r6_core.db",
    )
    critic = agent._critic_llm()
    assert isinstance(critic, LLMClient)
    assert critic is not agent.llm
    assert critic.provider == "kimi"
    # No reviewer configured -> the agent's own model is the critic
    monkeypatch.delenv("TITAN_REVIEWER_PROVIDER", raising=False)
    agent2 = TitanAgent(
        llm=gen,
        memory=MemoryManager(tmp_path / "r6b.db"),
        core_memory_path=tmp_path / "r6b_core.db",
    )
    assert agent2._critic_llm() is agent2.llm