# Titan Agent — Phase 3: Live-Loop Integration

Phase 3 wires the Phase 2 core engines (`core/reasoning`, `core/guardrails`, ...)
into the **production agent loop** and adds the frontier-class providers and a
headless runner from the 2026 agent comparison. This is what turns Titan from
"has the patterns" into "runs the patterns."

## 1. Strategy parameter — `run_task(..., strategy=...)`

`TitanAgent.run_task` accepts a new `strategy` argument with four values:

| strategy | pipeline | when to use |
|---|---|---|
| `auto` | classic prompt-driven loop (unchanged, byte-for-byte backward compatible) | default |
| `react` | structured `ReActEngine`: think → act → observe + live reflection | everyday tasks, tool-heavy work |
| `plan` | `PlanExecutor` builds a step plan (`plan` event), then `ReActEngine` executes it | multi-step refactors, research |
| `tot` | `ToTEngine` explores candidate strategies (Tree-of-Thoughts), then `ReActEngine` executes the winning path with real tools | hard, ambiguous problems |

Every structured strategy streams the same `AgentEvent` shape the classic loop
uses (`plan`, `thought`, `tool_call`, `tool_result`, `status`, `final_answer`,
`error`), so the Web UI, SSE endpoint and CLI need no changes. The final answer
is written to conversation memory.

If the structured layer fails mid-run, `run_task` emits an `error` event and
falls back to the classic loop — the agent never dies because of the new layer.

## 2. Adapters — `titan_agent/structured.py`

- `LLMBridge(ILLMProvider)` — adapts the production `LLMClient` (`chat_completion`)
  to the core `ILLMProvider` (`complete`, `complete_with_tools`).
- `ToolBridge(IToolExecutor)` — adapts `execute_tool_unified` to the core
  `IToolExecutor`, normalizing tool dicts to carry a top-level `name` that the
  core prompt helpers rely on.
- `ReflectorAdapter(IReflector)` — self-critique pass on the same model, returns
  `{insight, correction, halt}`.

## 3. Guardrails in the loop (Cline-style approval gates)

Every tool activation inside a structured run passes a `PolicyEngine`:

- `allow` → tool runs.
- `deny` → the tool returns `Error: blocked by safety policy (...)`; the ReAct
  loop observes the failure and picks an alternative tool.
- `require_approval` → a `HumanInTheLoop` request is raised and waited on
  (`hitl_timeout`); in autonomous mode (no responder) it auto-denies.
  `auto_approve=True` disables the gate for fully-trusted contexts.

Policies default to `DEFAULT_RULES` (blocks `rm -rf`, destructive commands,
screenshots-of-sensitive-paths, etc.). All decisions land in the audit trail.

## 4. New providers — Kimi K3 and GLM-5.3 Flash

| provider | vendor | base URL (default) | default model |
|---|---|---|---|
| `kimi` | Moonshot | `https://api.moonshot.cn/v1` | `kimi-k3` |
| `glm` | Zhipu | `https://open.bigmodel.cn/api/paas/v4` | `glm-5.3-flash` |

Both are OpenAI-compatible; set `KIMI_API_KEY` / `GLM_API_KEY` in `.env`
(optionally `KIMI_MODEL` / `GLM_MODEL` or `TITAN_MODEL`). Provider precedence
with no explicit choice: OpenRouter → Kimi → GLM → DeepSeek → Groq → OpenAI →
Ollama. Behaviour is unchanged until the new keys are present. DeepSeek remains
available (set `TITAN_MODEL=deepseek-v4.1-flash` to target the Flash variant).

## 5. Headless / CI runner

```bash
# CLI — exits 0 only when a final answer was produced (CI-friendly)
python -m titan_agent.headless "Refactor the login module" --strategy plan --mode deep
python -m titan_agent.headless "Summarize ./src" --json        # full event log
```

```python
from titan_agent.headless import run_headless, build_agent

code, final, events = run_headless(
    "task", strategy="plan", mode="deep", agent=build_agent(provider="kimi")
)
```

`build_agent()` mirrors the web server's exact wiring (same ToolRegistry, MCP,
memory, skills, telegram instances).

## 6. Files

| file | change |
|---|---|
| `titan_agent/structured.py` | **new** — bridges + `StructuredEngine` |
| `titan_agent/headless.py` | **new** — headless / CI runner + CLI |
| `titan_agent/agent.py` | `run_task` gains `strategy`; structured branch + `_build_structured_context` |
| `titan_agent/config.py` | `KIMI_*` / `GLM_*` keys + precedence |
| `titan_agent/llm_client.py` | `kimi` / `glm` provider credentials |
| `titan_agent/server.py` | `ChatRequest.strategy` + cron pass-through |
| `tests/test_phase3_structured.py` | **new** — 15 tests (bridges, guardrails, engine, dispatch, headless) |

## Verified

- `python -m pytest tests -q` → **193 passed**
- `python -m ruff check` on all changed files → clean
- CLI parsing verified (`--help`); server imports verified via the suite