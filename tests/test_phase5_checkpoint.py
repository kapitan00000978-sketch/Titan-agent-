"""Phase 5 — Devin-style session checkpoints / resume tests."""

import asyncio

from titan_agent.agent import TitanAgent
from titan_agent.checkpoint import CheckpointStore, RunCheckpoint
from titan_agent.llm_client import LLMResponse

# ---------- store primitives ----------


def test_store_round_trip(tmp_path):
    store = CheckpointStore(tmp_path / "cp.db")
    cp = RunCheckpoint(
        session_id="s1",
        user_input="fix login",
        mode="fast",
        effort="medium",
        strategy="react",
        messages=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}],
        steps_done=3,
        tools_used=["web_search", "write_file"],
        status="running",
    )
    store.save(cp)

    loaded = store.load("s1")
    assert loaded is not None
    assert loaded.session_id == "s1"
    assert loaded.user_input == "fix login"
    assert loaded.strategy == "react"
    assert loaded.steps_done == 3
    assert loaded.tools_used == ["web_search", "write_file"]
    assert loaded.messages == [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
    assert loaded.status == "running"


def test_store_save_overwrites_same_session(tmp_path):
    store = CheckpointStore(tmp_path / "cp.db")
    store.save(RunCheckpoint(session_id="s1", user_input="a", steps_done=1))
    store.save(RunCheckpoint(session_id="s1", user_input="b", steps_done=5, status="done", final_answer="ans"))
    loaded = store.load("s1")
    assert loaded.user_input == "b"
    assert loaded.steps_done == 5
    assert loaded.status == "done"
    assert loaded.final_answer == "ans"
    assert store.stats() == {"total": 1, "done": 1}


def test_store_list_newest_first_and_delete(tmp_path):
    store = CheckpointStore(tmp_path / "cp.db")
    store.save(RunCheckpoint(session_id="old", user_input="first"))
    store.save(RunCheckpoint(session_id="new", user_input="second"))
    sessions = [cp.session_id for cp in store.list()]
    assert sessions == ["new", "old"]
    assert store.delete("old") is True
    assert store.load("old") is None
    assert store.delete("old") is False


def test_store_load_missing_returns_none(tmp_path):
    store = CheckpointStore(tmp_path / "cp.db")
    assert store.load("nope") is None


# ---------- agent integration ----------


class FakeLLM:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = 0
        self.seen_messages = None

    async def chat_completion(self, messages, tools=None):
        self.calls += 1
        self.seen_messages = list(messages)
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content="Done: yes.")


def _run(agent, task, **kwargs):
    async def _go():
        return [ev async for ev in agent.run_task(task, session_id=kwargs.pop("session_id", "s"), **kwargs)]

    return asyncio.run(_go())


def test_run_task_always_on_checkpoint_marks_done(tmp_path):
    agent = TitanAgent(llm=FakeLLM(), checkpoint_path=tmp_path / "cp.db")
    events = _run(agent, "summarize the docs", mode="fast")
    assert any(ev.type == "final_answer" for ev in events)

    store = CheckpointStore(tmp_path / "cp.db")
    cp = store.load("s")
    assert cp is not None and cp.status == "done"
    assert cp.final_answer == "Done: yes."
    assert cp.user_input == "summarize the docs"


def test_run_task_records_tools_used(tmp_path):
    def _resp_with_tool():
        return LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "memory_save", "arguments": '{"key":"k","value":"v"}'},
                }
            ],
        )

    fake = FakeLLM(responses=[_resp_with_tool(), LLMResponse(content="saved the fact")])
    agent = TitanAgent(llm=fake, checkpoint_path=tmp_path / "cp.db")
    events = _run(agent, "remember something", mode="fast")
    assert any(ev.type == "tool_call" for ev in events)

    cp = CheckpointStore(tmp_path / "cp.db").load("s")
    assert cp.tools_used == ["memory_save"]
    assert cp.steps_done >= 1


def test_resume_restores_messages_and_emits_status(tmp_path):
    store = CheckpointStore(tmp_path / "cp.db")
    store.save(
        RunCheckpoint(
            session_id="s",
            user_input="finish the login work",
            messages=[
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "finish the login work"},
                {"role": "assistant", "content": "PARTIAL WORK DONE: auth module wired"},
            ],
            steps_done=4,
            status="running",
        )
    )

    fake = FakeLLM()
    agent = TitanAgent(llm=fake, checkpoint=store)
    events = _run(agent, "finish the login work", resume=True, mode="fast")

    assert any(ev.type == "status" and "Resuming session 's'" in str(ev.data) for ev in events)
    assert any(ev.type == "final_answer" for ev in events)
    # The LLM saw the restored checkpoint context, not a fresh conversation
    roles = [m["role"] for m in fake.seen_messages]
    assert "system" in roles
    assert any("PARTIAL WORK DONE" in str(m.get("content", "")) for m in fake.seen_messages)

    cp = CheckpointStore(tmp_path / "cp.db").load("s")
    assert cp.status == "done"


def test_resume_without_checkpoint_is_normal_run(tmp_path):
    fake = FakeLLM()
    agent = TitanAgent(llm=fake, checkpoint_path=tmp_path / "cp.db")
    events = _run(agent, "brand new task", resume=True, mode="fast")
    assert not any(ev.type == "status" and "Resuming" in str(ev.data) for ev in events)
    assert any(ev.type == "final_answer" for ev in events)


def test_resume_done_session_returns_saved_result_without_llm(tmp_path):
    store = CheckpointStore(tmp_path / "cp.db")
    store.save(
        RunCheckpoint(
            session_id="s",
            user_input="already done task",
            status="done",
            final_answer="the saved answer",
            messages=[{"role": "user", "content": "already done task"}],
        )
    )

    class _NoCallLLM:
        async def chat_completion(self, messages, tools=None):
            raise AssertionError("LLM must not be called for a completed session")

    agent = TitanAgent(llm=_NoCallLLM(), checkpoint=store)
    events = _run(agent, "already done task", resume=True, mode="fast")

    finals = [ev.data for ev in events if ev.type == "final_answer"]
    assert finals == ["the saved answer"]
    assert any(ev.type == "status" and "already completed" in str(ev.data) for ev in events)


def test_llm_error_records_error_status(tmp_path):
    class _FailingLLM:
        async def chat_completion(self, messages, tools=None):
            raise RuntimeError("test-llm-down")

    agent = TitanAgent(llm=_FailingLLM(), checkpoint_path=tmp_path / "cp.db")
    events = _run(agent, "will explode", mode="fast")
    assert any(ev.type == "error" for ev in events)
    cp = CheckpointStore(tmp_path / "cp.db").load("s")
    assert cp is not None and cp.status == "error"


def test_structured_success_marks_checkpoint_done(tmp_path):
    """A plan/react/tot run saves the checkpoint as done with its final answer."""
    agent = TitanAgent(llm=FakeLLM(), checkpoint_path=tmp_path / "cp.db")
    events = _run(agent, "structured task", strategy="react", mode="fast")
    assert any(ev.type == "final_answer" for ev in events)
    cp = CheckpointStore(tmp_path / "cp.db").load("s")
    assert cp is not None and cp.status == "done"


# ---------- pass-through ----------


def test_headless_and_server_expose_resume():
    import inspect

    from titan_agent.headless import run_headless
    from titan_agent.server import ChatRequest

    assert "resume" in inspect.signature(run_headless).parameters
    assert ChatRequest(message="x").resume is False
    assert ChatRequest(message="x", resume=True).resume is True