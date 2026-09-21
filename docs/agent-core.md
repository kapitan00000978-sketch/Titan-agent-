# Titan Agent Core — Advanced Agent Patterns

Phase 2 of the Titan Agent upgrade: the strongest patterns from the 2026 agent
comparison (Claude Code, Codex, Cursor, Copilot, Devin, Windsurf, OpenCode, Aider,
Cline, Replit, Gemini CLI, Cody, Tabnine) implemented as a modular, dependency-free
core under `titan_agent/core/`.

> **Phase 3 (2026)** — these patterns are now wired into the live agent loop:
> `run_task(..., strategy="plan|react|tot")` runs the core engines with policy
> guardrails, `kimi`/`glm` frontier providers were added, and a headless/CI runner
> ships in `titan_agent/headless.py`. See `docs/phase3-integration.md`.
>
> **Phase 4 (2026)** — `gitops.py` brings Aider-style git-first tools
> (`git_status`/`git_diff`/`git_commit` + end-of-run auto-commit), and the
> `core/memory` `MemorySystem` is wired into the live loop: every completed run is
> recorded as an episodic memory and recalled into context on later runs.
> See `docs/phase4-gitops-memory.md`.
>
> **Phase 5 (2026)** — `checkpoint.py` brings Devin-style session continuity:
> runs checkpoint themselves always-on (live messages + steps + tools + status)
> and `run_task(..., resume=True)` restores an interrupted session or replays a
> completed one (no LLM call). See `docs/phase5-checkpoint-resume.md`.
>
> **Phase 6 (2026)** — `omni` provider: a self-hosted AI gateway
> (`localhost:20128/v1`) exposed as six auto-routing virtual models
> (`auto` / `auto/coding` / `auto/fast` / `auto/smart` / `auto/offline` /
> `auto/cheap`) — one key, smart per-request routing. Precedence chain now
> OpenRouter → OmniRoute → Kimi → GLM → DeepSeek → Groq → OpenAI → Ollama.
> See `docs/phase6-omni.md`.

All seven patterns are covered — one package each — built on typed interfaces so
engines and providers can be swapped without touching callers.

```
titan_agent/core/
├── __init__.py
├── reasoning/      # ReAct + Plan-and-Execute + Tree of Thoughts
│   ├── types.py        # ReasoningStep/Plan/ReasoningTrace/ReasoningConfig
│   ├── interfaces.py   # ILLMProvider, IToolExecutor, IPlanner, IReflector,
│   │                   # IEvaluator, IReasoningEngine, ReasoningContext
│   ├── react.py        # ReActEngine (think→act→observe + reflection)
│   ├── planner.py      # PlanExecutor (create/replan, deps)
│   └── tot.py          # ToTEngine + LLMEvaluator (beam search)
├── memory/          # MemGPT/Mem0-style memory
│   ├── types.py        # MemoryKind/MemoryRecord/MemoryQuery/MemoryStats
│   └── memory_system.py# MemorySystem (SQLite, consolidation, decay)
├── reflection/      # Devin/Reflexion-style self-correction
│   └── reflector.py    # Reflector + LessonStore
├── orchestration/   # AutoGen/LangGraph-style multi-agent
│   ├── types.py        # AgentRole/AgentSpec/AgentMessage/AgentResult
│   └── orchestrator.py # AgentTeam (4 coordination modes)
├── guardrails/      # Constitutional AI + HITL
│   ├── policy.py       # PolicyEngine, Rule, Decision, audit trail
│   └── hitl.py         # HumanInTheLoop, ApprovalRequest
└── tools/           # Cursor/Codex-style tool layer
    └── registry.py     # ToolRegistry, ToolSpec, discovery, compose, sandbox
```

---

## 1. Reasoning — `titan_agent/core/reasoning/`

### Interfaces
Implemented by providers/engines elsewhere; engines only depend on these:

- `ILLMProvider.complete(messages, temperature, max_tokens, stream)` and
  `complete_with_tools(messages, tools, ...)` — native function calling.
- `IToolExecutor.execute(name, args, context)` / `get_available_tools()` / `has_tool(name)`.
- `IPlanner.create_plan(goal, context, available_tools)` / `replan(plan, failed_step, error, context)`.
- `IReflector.reflect(trace, focus)` / `should_continue(trace)`.
- `IEvaluator.evaluate(trace, candidates)` / `is_solution(trace, goal)` — ToT scoring.
- `IReasoningEngine.reason(task, config, trace)` / `stream_reason(task, config)`.

### `ReActEngine` (`react.py`)
```
loop (max_steps):
  decision = LLM(messages)                 # thought + action (+ action_input)
  if action == final_answer: yield DECIDE  ; return
  result = tools.execute(action, args)     # failure -> FAILED step, not crash
  yield ACT step; append [OBSERVATION] to history
  every reflection_interval -> Reflector pass (insight fed back, can halt)
```
- Text fallback parses `{"thought","action","action_input"}` JSON; garbage output
  is treated as a final answer rather than a crash.
- `_parse_tool_response` handles native tool-calling dicts.

### `PlanExecutor` (`planner.py`)
- LLM produces a JSON plan (steps with `tool_name`, `tool_args`,
  `expected_outcome`, `dependencies`).
- `Plan.get_ready_steps()` only returns steps whose dependencies are completed.
- `replan()` re-runs planning with failure context and preserves completed steps.

### `ToTEngine` + `LLMEvaluator` (`tot.py`)
```
beam = [root]
for depth in range(tot_max_depth):
  expanded = for each path: LLM generates b distinct next-thoughts
  scores = evaluator.evaluate(root, expanded)
  beam    = top-b by score            # score stored in metadata, not steps
  if evaluator.is_solution(cand, task): return cand
return beam[0] best-effort answer
```
- `LLMEvaluator` is a concrete `IEvaluator` using an LLM for scoring and
  solution detection; scores are clamped to 0..1 and padded to candidate count.

### Config
`ReasoningConfig` bounds: `max_steps` (≤100), `max_observation_tokens` (≤20k),
`max_plan_steps` (≤50), `max_retries_per_step` (≤10), `reflection_interval` (≤10),
`max_reflection_turns` (≤5), `tot_branching_factor` (2–5), `tot_max_depth` (≤5).

---

## 2. Memory — `titan_agent/core/memory/`

### `MemorySystem`
- **Episodic** (`EPISODIC`): what happened — tasks, outcomes.
- **Semantic** (`SEMANTIC`): consolidated facts.
- **Procedural** (`PROCEDURAL`): how-to lessons (used by `Reflector`/`LessonStore`).
- **Working** (`WORKING`): in-process ephemeral context (`remember_working`),
  never persisted to SQLite.

### Retrieval scoring
```
score = keyword_overlap * 0.6
      + recency(1/(1+days)) * 0.2
      + importance * 0.15
      + min(1, access_count/10) * 0.05
```
`recall()`/`query()` rank by score, respect `min_score` / `min_importance`,
filter by `kinds` and `scope`, and bump `access_count` on returned records.

### Consolidation
`consolidate(min_importance=0.6)` groups high-importance episodes by scope and
writes a deduplicated semantic fact (importance = max + 0.1, `source_count`
metadata), returning a `ConsolidationResult`.

### Lifecycle
`forget(older_than_days, kind, min_importance)` deletes expired low-value
records; `clear()` and `stats()` round out the API. Every connection is
context-managed and closed — Windows file-lock safe.

---

## 3. Reflection — `titan_agent/core/reflection/`

- **`Reflector(llm, lesson_store?, max_trace_steps)`** — formats the last N trace
  steps (think / act / reflect, with error info), asks the LLM for
  `{"insight","correction","halt","confidence"}`, and — when the trace tail
  contained failures — persists the correction as a lesson.
- **`LessonStore(memory?)`** — procedural memory wrapper; `record_lesson()` saves
  with an importance boosted by confidence; `get_relevant_lessons(context)` recalls
  matching lessons before a future run.
- `should_continue()` returns false when a prior reflection set `halt: true`.

---

## 4. Orchestration — `titan_agent/core/orchestration/`

### `AgentTeam(llm, agents?)`
- `register_role(role, system_prompt, name?, model_hint?)` / `register(spec)`;
  duplicate roles raise `ValueError`.
- `run_agent(role, task, context?) -> AgentResult` — one typed agent, errors
  captured in `AgentResult` (never throw into the team).

### Coordination modes (`OrchestrationMode`)
| Mode | Behavior |
|---|---|
| `SEQUENTIAL` | pipeline of roles, each sees the previous output; stops on first error |
| `PARALLEL` | `asyncio.gather` fan-out; outputs joined with separators |
| `CONSENSUS` | all roles answer; majority vote via `Counter`, confidence = share |
| `SUPERVISOR` | supervisor plans → specialists work → supervisor synthesizes `final` |

Result container: `TeamRunResult` keeps per-role `AgentResult`s, a `trace`, and
timestamps.

---

## 5. Guardrails — `titan_agent/core/guardrails/`

### `PolicyEngine`
- `Rule(action, resource, effect, reason)` with prefix-matched resources;
  default rules deny destructive commands (`rm -rf`, `format c:`, `mkfs`,
  `shutdown`), require approval for `delete_file` and `screenshot`, and deny
  private-network targets (SSRF).
- `check(action, resource, content)` — merges rule + content checks (DENY wins,
  then REQUIRE_APPROVAL); every decision is written to the in-memory audit list
  and optional JSONL file.
- `check_network_target(url)` — explicit SSRF guard (127.x, 10.x, 192.168.x,
  172.16–31, localhost, IPv6 ULA).
- `find_sensitive(content)` — flags API keys, secrets, passwords, base64 blobs,
  credit-card-length digit runs.

### `HumanInTheLoop`
- `request(action, resource, details, reason)` → `ApprovalRequest` (pending).
- `await wait(req, timeout)` — resolves on `approve`/`deny`, or moves to
  `TIMED_OUT`; `decide()` centralizes state transitions and audit logging.
- `status_counts()` for dashboards.

---

## 6. Tools — `titan_agent/core/tools/`

### `ToolRegistry(delegate, policy?, workspace?, require_approval_for?)`
Wraps any executor with the `tools.ToolRegistry` shape (definitions +
`tool_*` handlers); also implements `IToolExecutor` so it can drive `ReActEngine`.

| Feature | API |
|---|---|
| Discovery | `discover(query, category, max_risk, limit)`, `get(name)`, `all_specs()` |
| Typed specs | `ToolSpec` (category / risk / parameters / requires_approval) |
| Policy gate | every `execute()` checks `PolicyEngine` first; command text is the resource |
| Sandbox | path args resolved inside `workspace`; escapes → `PermissionError` |
| Composition | `compose([(name, args), ...])` with `{"$result": i, "$path": "k"}` templates |
| Parallel | `run_parallel([(name, args), ...])` via `asyncio.gather` |
| Stats | `stats()` — totals by category and risk |

### Integration examples

```python
from titan_agent.core.tools import ToolRegistry
from titan_agent.core.guardrails import PolicyEngine
from titan_agent.core.reasoning import ReActEngine, ReasoningConfig
from titan_agent.core.reasoning.interfaces import ILLMProvider

# 1. Wrap the real tool registry behind policy + sandbox
tools = ToolRegistry(delegate=your_tool_registry, policy=PolicyEngine(),
                     workspace=your_workspace_path)

# 2. Drive it with ReAct — denials become observations, agent recovers
engine = ReActEngine(llm=your_llm, tools=tools,
                     config=ReasoningConfig(max_steps=10, reflection_interval=4))
trace = await engine.reason("investigate and fix the timeout bug")

# 3. Chain tools: search result feeds the next call
outputs = await tools.compose([
    ("web_search", {"query": "titan agent"}),
    ("deep_search", {"topic": {"$result": 0}}),
])
```

---

## Tests

| File | Coverage |
|---|---|
| `tests/test_phase1.py` | config_v2, exceptions, DI (18) |
| `tests/test_phase2_reasoning.py` | ReAct + PlanExecutor + plan types (13) |
| `tests/test_phase2_tot.py` | ToT beam search + LLMEvaluator (8) |
| `tests/test_phase2_memory.py` | memory store, scoring, consolidation (19) |
| `tests/test_phase2_agents.py` | reflection, orchestration, guardrails (31) |
| `tests/test_phase2_tools.py` | discovery, policy, compose, sandbox, ReAct integration (17) |

**Total: 178 passed; ruff clean on `titan_agent/core/`.**

### Extension guide
- **New provider**: implement `ILLMProvider`, register in DI `ServiceRegistry`.
- **New engine**: implement `IReasoningEngine` (or subclass an existing one), export
  from its package `__init__.py`.
- **New tool**: add a `tool_<name>` method to a delegate + definition in
  `get_tool_definitions()`; the core `ToolRegistry` picks it up automatically.
- **New guardrail**: add a `Rule` to `PolicyEngine` or a phrase/pattern to the
  content checkers.