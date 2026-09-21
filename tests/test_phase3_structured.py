"""
Phase 3 tests — live-loop integration of the core engines.

Covers: LLMBridge / ToolBridge adapters, policy guardrail gating, the
StructuredEngine (react / plan), the run_task `strategy` dispatch, and the
headless/CI runner.
"""
import asyncio

from titan_agent.agent import TitanAgent
from titan_agent.core.guardrails.policy import PolicyEngine, Rule
from titan_agent.headless import run_headless
from titan_agent.llm_client import LLMResponse
from titan_agent.structured import LLMBridge, StructuredEngine, ToolBridge


class FakeLLM:
    """Scripted replacement for LLMClient.chat_completion."""

    def __init__(self, script=None, default=None):
        self.script = list(script or [])
        self.default = default or LLMResponse(content="Fallback done")
        self.calls = 0

    async def chat_completion(self, messages, tools=None, temperature=0.6, max_tokens=4096):
        self.calls += 1
        if self.script:
            resp = self.script.pop(0)
            if callable(resp):
                return resp(messages, tools)
            return resp
        return self.default

    @property
    def provider(self):
        return "fake"

    @property
    def model(self):
        return "fake-test"


SIMPLE_TOOL = {
    "type": "function",
    "function": {"name": "execute_command", "description": "run a shell command", "parameters": {"type": "object"}},
}


def tool_call_resp(name, args_json):
    return LLMResponse(
        content="using tools",
        tool_calls=[{"id": "c1", "type": "function", "function": {"name": name, "arguments": args_json}}],
    )


# --------------------------------------------------------------------------
# Bridge adapters
# --------------------------------------------------------------------------

def test_llm_bridge_complete_returns_content():
    fake = FakeLLM([LLMResponse(content="hello")])
    bridge = LLMBridge(fake)

    async def _run():
        return await bridge.complete([{"role": "user", "content": "hi"}])

    assert asyncio.run(_run()) == "hello"


def test_llm_bridge_complete_with_tools_returns_dict():
    fake = FakeLLM([tool_call_resp("execute_command", '{"command":"dir"}')])
    bridge = LLMBridge(fake)

    async def _run():
        out = await bridge.complete_with_tools([{"role": "user", "content": "hi"}], [SIMPLE_TOOL])
        return out

    out = asyncio.run(_run())
    assert out["tool_calls"][0]["function"]["name"] == "execute_command"


def test_tool_bridge_policy_denies_destructive_command():
    calls = []
    policy = PolicyEngine(rules=[Rule("execute_command", "rm -rf", "deny", "destructive")])

    async def execute(name, args):
        calls.append((name, args))
        return "ok"

    bridge = ToolBridge(execute, lambda: [SIMPLE_TOOL], policy_engine=policy)

    async def _run():
        blocked = await bridge.execute("execute_command", {"command": "rm -rf /tmp/x"})
        allowed = await bridge.execute("execute_command", {"command": "dir"})
        return blocked, allowed

    blocked, allowed = asyncio.run(_run())
    assert "blocked" in blocked
    assert allowed == "ok"
    assert [c[0] for c in calls] == ["execute_command"]


def test_tool_bridge_approval_denied_without_responder():
    policy = PolicyEngine(rules=[Rule("delete_file", "*", "require_approval", "needs consent")])

    async def execute(name, args):
        return "deleted"

    bridge = ToolBridge(execute, lambda: [SIMPLE_TOOL], policy_engine=policy, hitl=None)

    async def _run():
        return await bridge.execute("delete_file", {"path": "C:/x.txt"})

    result = asyncio.run(_run())
    assert "approval required" in result


def test_tool_bridge_auto_approve_allows():
    policy = PolicyEngine(rules=[Rule("delete_file", "*", "require_approval", "needs consent")])
    calls = []

    async def execute(name, args):
        calls.append(name)
        return "deleted"

    bridge = ToolBridge(execute, lambda: [SIMPLE_TOOL], policy_engine=policy, hitl=None, auto_approve=True)

    async def _run():
        return await bridge.execute("delete_file", {"path": "C:/x.txt"})

    assert asyncio.run(_run()) == "deleted"
    assert calls == ["delete_file"]


def test_tool_bridge_has_tool_with_top_level_name():
    async def execute(name, args):
        return "ok"

    bridge = ToolBridge(execute, lambda: [SIMPLE_TOOL], policy_engine=None)
    assert bridge.has_tool("execute_command")
    assert not bridge.has_tool("nope")
    names = [t.get("name") for t in bridge.get_available_tools()]
    assert "execute_command" in names


# --------------------------------------------------------------------------
# StructuredEngine
# --------------------------------------------------------------------------

def test_structured_react_loop_yields_all_event_types():
    fake = FakeLLM(
        [
            tool_call_resp("execute_command", '{"command":"dir"}'),
            LLMResponse(content="Done: files are a.py, b.py"),
        ]
    )
    calls = []

    async def execute(name, args):
        calls.append((name, args))
        return "files: a.py b.py"

    engine = StructuredEngine(fake, execute, lambda: [SIMPLE_TOOL], policy_engine=None)

    events = asyncio.run(_collect(engine.run("list files", None, strategy="react", max_steps=6)))
    types = [e.type for e in events]
    assert "tool_call" in types and "tool_result" in types and "final_answer" in types
    final = next(e for e in events if e.type == "final_answer")
    assert "Done: files are a.py" in final.data
    assert calls == [("execute_command", {"command": "dir"})]


def test_structured_plan_strategy_emits_plan_event():
    plan_json = '{"steps":[{"description":"Step one","tool_name":"execute_command","expected_outcome":"listed","dependencies":[]}]}'
    fake = FakeLLM([LLMResponse(content=plan_json), LLMResponse(content="Done via plan")])

    async def execute(name, args):
        return "ok"

    engine = StructuredEngine(fake, execute, lambda: [SIMPLE_TOOL], policy_engine=None)

    events = asyncio.run(_collect(engine.run("do thing", None, strategy="plan", max_steps=6)))
    types = [e.type for e in events]
    assert "plan" in types
    plan_ev = next(e for e in events if e.type == "plan")
    assert plan_ev.data["count"] == 1
    assert "final_answer" in types


def test_structured_llm_error_surfaces_error_event():
    class BoomLLM:
        async def chat_completion(self, messages, tools=None, temperature=0.6, max_tokens=4096):
            raise RuntimeError("API down")

    async def execute(name, args):
        return "ok"

    engine = StructuredEngine(BoomLLM(), execute, lambda: [SIMPLE_TOOL], policy_engine=None)
    events = asyncio.run(_collect(engine.run("x", None, strategy="react", max_steps=6)))
    assert any(e.type == "error" for e in events)


# --------------------------------------------------------------------------
# run_task strategy dispatch
# --------------------------------------------------------------------------

def _collect(agen):
    async def _run():
        return [ev async for ev in agen]

    return _run()


def test_run_task_strategy_react_yields_final():
    fake = FakeLLM([LLMResponse(content="Final structured answer")])
    agent = TitanAgent(llm=fake)

    events = asyncio.run(_collect(agent.run_task("hello", session_id="t3", strategy="react")))
    types = [e.type for e in events]
    assert "final_answer" in types
    assert any(t == "status" for t in types)
    final = next(e for e in events if e.type == "final_answer")
    assert "Final structured answer" in final.data


def test_run_task_auto_keeps_classic_loop():
    fake = FakeLLM([LLMResponse(content="Classic answer")])
    agent = TitanAgent(llm=fake)

    events = asyncio.run(_collect(agent.run_task("hello", session_id="t4", mode="fast", strategy="auto")))
    types = [e.type for e in events]
    assert "step_start" in types  # legacy loop marker
    assert not any(t == "plan" for t in types)
    assert not any(e.type == "status" and "Structured reasoning" in str(e.data) for e in events)


def test_run_task_invalid_strategy_falls_back_to_auto():
    fake = FakeLLM([LLMResponse(content="Classic answer")])
    agent = TitanAgent(llm=fake)

    events = asyncio.run(_collect(agent.run_task("hello", session_id="t5", strategy="bogus")))
    types = [e.type for e in events]
    assert "step_start" in types  # classic loop ran


# --------------------------------------------------------------------------
# Headless runner
# --------------------------------------------------------------------------

def test_headless_returns_answer_and_exit_0():
    fake = FakeLLM([LLMResponse(content="headless done")])
    agent = TitanAgent(llm=fake)

    code, final, events = run_headless("task", strategy="react", agent=agent)
    assert code == 0
    assert "headless done" in final
    assert events, "expected event log"
    assert all("type" in e for e in events)


def test_headless_no_answer_exit_1():
    class BrokenLLM:
        async def chat_completion(self, messages, tools=None, temperature=0.6, max_tokens=4096):
            raise RuntimeError("provider down")

    agent = TitanAgent(llm=BrokenLLM())
    code, final, events = run_headless("task", strategy="react", agent=agent)
    assert code == 1
    assert final == ""
    assert any(e.get("type") == "error" for e in events)


def test_build_agent_provider_override(monkeypatch):
    from titan_agent.headless import build_agent

    monkeypatch.setattr("titan_agent.headless.ToolRegistry", lambda _: object())
    monkeypatch.setattr("titan_agent.headless.MCPManager", lambda _: object())
    monkeypatch.setattr("titan_agent.headless.MemoryManager", lambda: object())
    monkeypatch.setattr("titan_agent.headless.SkillRegistry", lambda: object())
    monkeypatch.setattr("titan_agent.headless.TelegramManager", lambda: object())

    agent = build_agent(provider="kimi", model="kimi-k3")
    assert agent.llm.provider == "kimi"
    assert agent.llm.model == "kimi-k3"