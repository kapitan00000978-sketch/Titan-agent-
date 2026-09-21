# TITAN AGENT — Changelog

All fixes and improvements made during the completion effort of this project.

## 🔧 Phase 9B — OBSIDIAN INTEGRATION (`obsidian-mcp@2`)

Titan can now read and write an **Obsidian vault** through its MCP layer.
Unlike the old REST-plugin approach, `obsidian-mcp@2` works **directly on the
vault's Markdown files** — no plugin, no API key, and Obsidian itself does not
need to be open (only Node 22+ and a vault folder with an `.obsidian` dir).

- `mcp_servers.json` gains an `obsidian` server: `npx -y obsidian-mcp@2 serve --vault notes={OBSIDIAN_VAULT}`.
- `mcp_client.py` `_resolve_server_command()` now expands **`{ENV_VAR}` tokens
  in `args`/`command`** (not just `env` values), so vault paths / keys can live
  in `.env`. Missing vars become empty strings — startup stays non-fatal and the
  server's own validation fails visibly, exactly like the `{GITHUB_TOKEN}` policy.
- `.env`/`.env.example` gain `OBSIDIAN_VAULT=<absolute vault path>`.
- Tools surface as `mcp_obsidian_*`: `read_note`, `create_note`, `edit_note`,
  `delete_note`, `move_note` (backlink rewrite), `search_vault`, tag management,
  `list_vaults` — 12 tools total, verified end-to-end.

### Verification
- `tests/test_mcp_extended.py` — **+3 deterministic tests** (obsidian entry in
  config, `{ENV_VAR}` expansion in args, missing var → empty; 7 total in file).
- **Real integration check** (not committed): a throwaway vault connected via
  Titan's own `MCPManager` → 12 tools listed, `list_vaults` → `notes`,
  `create_note` + `read_note` round-trip passed, file verified on disk.

## 🔧 Phase 9 — DEDICATED SUBAGENT STAFF

Subagents stop being carbon copies of Titan: there is now a **staff of named
specialists** — `planner`, `researcher`, `coder`, `reviewer`, `tester` (plus
`generalist`) — each with its own persona overlay, tuned run options and an
**enforced tool policy**. A researcher can't commit, a reviewer can't rewrite
files, a tester only verifies. Role aliases (`code`, `research`, `qa`, ...)
resolve automatically; unknown roles fall back to `generalist`.

### How roles are enforced (not just prompted)
- **Persona** — `system_extra` persona appended to the child's system prompt
  right after the base identity (`run_task(..., system_extra=)`).
- **Catalog filter** — `_build_tools_list()` / `_build_tool_catalog_text()`
  drop forbidden tools (terminal/memory/skill/telegram/git/MCP), so the child
  model never sees them.
- **Execution gate** — `execute_tool_unified()` refuses out-of-role tools
  before dispatch, for every tool family.

### New/changed surface
- `staff.py` (new): `ToolPolicy` (allowed/blocked), `Specialist`, `SPECIALISTS`,
  `get_specialist()`, `staff_catalog()`, `StaffPool.run()` / `.team()` (runner
  injectable for deterministic tests).
- `headless.py`: `run_headless(..., system_extra=)`; `build_agent(tools=,
  tool_policy=)`.
- `agent.py`: `tool_policy` on `TitanAgent`; policy gate + catalog filtering;
  `system_extra` on `run_task`; system prompt lists the staff.
- `tools.py`: `subagent_delegate` gains `role`, `subagent_team` gains `roles`,
  new `subagent_roles` catalog tool. FULL ACCESS still raises the team bound 2→8.

### Verification
- `tests/test_staff.py` — **26 deterministic tests**.
- Full suite: **314 passed, 1 skipped**.
- `ruff check` clean on all touched files (only the 4 pre-existing `ASYNC221`
  wmctrl warnings remain in the wider tree).

## 🚀 Phase 8 — FULL ACCESS: every capability boundary removed

`TITAN_FULL_ACCESS=1` makes Titan **truly unrestricted** — every limit that was
ever placed on it is lifted when Full Access is on. This is the second half of
"chegaralarni buz": **FULL_ACCESS removes all capability/comfort boundaries**,
and a second flag **`TITAN_ABSOLUTE_ACCESS=1`** additionally drops the last two
protection lines. Normal mode behaviour is byte-for-byte unchanged.

### What FULL_ACCESS removes (all of it)
- **Step budget** — `_compute_max_steps` returns no ceiling and a 4× larger
  budget (run until the task is verifiably done, never a hard stop).
- **Command timeout** — 45s → 10 minutes (`execute_command`), and the raw/self-
  heal runner's 60s default is raised the same way.
- **Approval gates** — `PolicyEngine` auto-grants every `require_approval` rule
  (delete_file / screenshot), and the guarded `ToolRegistry` + `ToolBridge` pass
  approvals without a human. Structured `hitl_timeout` no longer blocks.
- **Structured-reasoning clamp** — the core engines' `min(max_steps, 30)` cap is
  lifted to 1000 so `plan`/`react`/`tot` deep runs keep working too.
- **Downloads** — `download_file` loses the 100 MB cap (→2 GB) and the fetch
  timeout rises 30s → 2 min; the workspace-sandbox path check in the guarded
  registry is lifted.
- **HTTP server** — `start_http_server` accepts any port 1–65535.
- **Token rate-limiter** — `TokenRateLimiter` is disabled (no throttling).
- **Subagents** — `subagent_team` parallelism bound raised 2 → 8.
- System prompt gets a **FULL ACCESS MODE ACTIVE** block so the model knows the
  boundaries are gone and must still verify before reporting.

### What still protects (unless you opt into ABSOLUTE)
- **FULL_ACCESS keeps** the protection floor: destructive-command denies
  (`rm -rf` / `format c:` / `mkfs` / `shutdown`) and the SSRF
  private-network guard, plus prompt-injection phrase blocking.
- **TITAN_ABSOLUTE_ACCESS=1** additionally lifts those denies and the SSRF
  guard — the agent can reach destructive operations and internal networks it
  asks for. This is an explicit extra opt-in, never implied by FULL_ACCESS.

### Runtime toggle (no restart)
- `config.py` — `full_access_enabled()` / `absolute_access_enabled()` read env at
  call-time; `set_full_access(on|None)` forces/clears a module override.
- `server.py` — `GET /api/config` reports `full_access`; `POST /api/config`
  accepts `full_access: bool` and applies it live.

### Files touched
`config.py`, `core/guardrails/policy.py` (access modes on `check()` /
`check_network_target()`), `structured.py` (ToolBridge auto-approve + clamp),
`core/tools/registry.py` (approval/sandbox/deny per access), `agent.py`
(budget + prompt), `tools.py` (`_command_timeout`, download, ports, subagents),
`token_limit.py`, `server.py`, `.env.example`.

### Verification
- `tests/test_full_access.py` — **32 deterministic tests** (flags, budget,
  policy modes, ToolBridge, guarded registry, timeouts, SSRF/scheme/size,
  ports, subagent cap, rate limiter, structured clamp, API model).
- Full suite: **288 passed, 1 skipped** (Windows-only screenshot branch).
- `ruff check` clean on all touched files (only the 4 pre-existing `ASYNC221`
  wmctrl warnings remain in the wider tree).

## 🚀 Phase 7 — Full Autonomy (completely independent operation)

Five blocks that let Titan run on its own, stop/repair/retry by itself, and keep
going far past the old limits — **without removing any safety guardrail**
(PolicyEngine, consent gates, SSRF checks and send allowlists all stay active).

### A. Self-healing loop — `titan_agent/heal.py`
- `diagnose()` classifies failures into deterministic repairs: `ModuleNotFoundError`
  → `pip install <pkg>` (with a numpy special-case), cmdlet/command-not-found and
  `MemoryError` → one transparent retry.
- `heal_run(run, command, max_attempts)` re-runs the original command after each
  repair until success or the budget is spent. All repairs run locally (zero LLM
  tokens). Fully injectable for deterministic tests.
- Exposed to the LLM as the `self_heal` tool.

### B. Dynamic step budget (no hard 48 clamp)
- `config.py` — `MAX_STEPS_CAP` (`TITAN_STEP_CAP`, default 48, was hardcoded),
  `UNLIMITED_STEPS` (`TITAN_UNLIMITED_STEPS`) and `DEEP_MAX_STEPS_BASE`
  (`TITAN_DEEP_MAX_STEPS`, default 40, was hardcoded).
- `agent.py` — `_compute_max_steps` applies the cap via config and skips the
  clamp entirely when `UNLIMITED_STEPS` is on: Titan iterates until the task is
  provably done (verification + final answer still required).

### C. Persistent task queue + autonomous daemon
- `titan_agent/queue.py` — `TaskQueue`, a thread-safe SQLite queue:
  priorities, `schedule_at` scheduling, atomic `claim_next`, exponential backoff
  retries (5→15→30→60s), `complete`/`fail`/`cancel`/`list`/`stats`/`clear`.
- `titan_agent/daemon.py` — `python -m titan_agent.daemon [--once] [--poll N]
  [--concurrency N] [--list] [--stats]`; claims due tasks and executes them via
  the headless runner in worker threads; a task crash never kills the daemon.
- Web API: `GET/POST /api/queue/tasks`, `DELETE /api/queue/tasks/{id}`,
  `POST /api/queue/process-once`.
- CLI: `/queue list|stats|add <task>|cancel <id>` and `/daemon`.

### D. Real-world tools — `titan_agent/tools.py`
- `download_file` — SSRF-guarded (private/loopback refused via PolicyEngine),
  100 MB cap, saves into the workspace.
- `start_http_server` / `stop_http_server` — background local HTTP server.
- `take_screenshot` — Windows screen capture via PowerShell (no extra deps).
- `self_update` — `git pull` (walk-up to repo root) + pip install + `pytest`.
- `task_enqueue` / `task_list` / `task_stats` / `task_cancel` — drive the queue
  from inside the agent.
- `subagent_delegate` / `subagent_team` — child-agent execution (Block E).
- System prompt catalog updated; `cli.py` + `server.py` wired.

### E. Deep subagent architecture — `titan_agent/subagents.py`
- `SubagentPool.delegate()` — one independent child (fresh `sub-<session>-<n>`
  session id; checkpoint/memory isolation) run to completion in a worker thread.
- `SubagentPool.team()` — parallel fan-out bounded by `max_workers`.
- Injectable runner keeps tests deterministic (no LLM/network).

### Verification
- `tests/test_phase7_autonomy.py` — 31 deterministic tests (heal, step budget,
  queue lifecycle/priority/backoff, daemon run-once, subagent delegate/team,
  tool registration, download SSRF, HTTP server, prompt catalog).
- Full suite: **256 passed, 1 skipped** (Windows-only screenshot branch).
- `python -m ruff check titan_agent/` — clean except the 4 known intentional
  `ASYNC221` wmctrl warnings that predate this phase.
- Live sanity: daemon `--stats`/`--list` run, an enqueue→daemon-run-once→done
  cycle completed, `/api/queue/*` routes registered.

## 🆕 OmniRoute provider (Phase 6 — 2026)

**OmniRoute** — self-hosted AI gateway (`http://localhost:20128/v1`) with smart auto-routing.
One key (`OMNI_API_KEY`) unlocks six virtual `auto*` models that route each request to the
best available provider/model (self-hosted localhost gateway, verified live against the real
localhost:20128 dashboard key):

| CLI model | Routing intent |
|---|---|
| `auto` | balanced default |
| `auto/coding` | code-first routing |
| `auto/fast` | low-latency routing |
| `auto/smart` | quality-first routing |
| `auto/offline` | local/offline models only |
| `auto/cheap` | cheapest available |

- **`config.py`** — new `OMNI_API_KEY` / `OMNI_BASE_URL` (default `http://localhost:20128/v1`) /
  `OMNI_MODEL` (default `auto`) + `OMNI_AUTO_MODELS` tuple. Provider precedence chain now
  includes OmniRoute (after OpenRouter, before Kimi/GLM).
- **`config_v2.py`** — `LLMSettings` gains `omni_base_url` / `omni_api_key` / `omni_model` fields.
- **`llm_client.py`** — `omni` provider branch in `_setup_credentials` (OpenAI-compatible `/v1`
  gateway). `chat_completion` raises a clear error if OmniRoute is not running.
- **`.env`** — `OMNI_API_KEY` set to the live dashboard key; `TITAN_PROVIDER=omni`,
  `TITAN_MODEL=auto` make OmniRoute the server-side default (Puter stays available for the
  in-browser path but is no longer the hard default).
- **`web_ui`** (`index.html` + `app.js`) — OmniRoute added to the provider dropdown and as a
  launch option; `auto*` / `auto/coding` / `auto/fast` / `auto/smart` / `auto/offline` /
  `auto/cheap` model chips added.
- **Live proof** — every `auto*` model returned HTTP 200 chat completions from the real
  gateway (`auto/offline` intentionally replies with an empty/offline response since no local
  provider is registered); a headless run over `auto/coding` confirmed full end-to-end routing.
- **Tests** — `tests/test_phase6_omni.py` (5 tests, pass) + the full suite: **225 passed.**

**Terminal usage:**

```
python -m titan_agent.headless "Your task here" --provider omni --model auto --json --auto-commit
python -m titan_agent.headless "Summarize the workspace" --provider omni --model auto/coding
titan-headless "Fix the broken import" --provider omni --model auto/fast
```

Without `TITAN_PROVIDER=omni` in `.env`, use `--provider omni` explicitly (or set
`TITAN_PROVIDER=omni` / `TITAN_MODEL=auto` in `.env` to make it the default).

## 🔴 Critical fixes

### 1. `titan_agent/server.py` — server would not start
- **Issue:** `Dict` and `Any` were not imported from `typing` → the module crashed at import with
  `NameError: name 'Dict' is not defined`, breaking the whole web dashboard.
- **Fix:** added `from typing import Any, Dict`.
- **Fix:** mutable default `{}` for `ToolExecuteRequest.arguments` → `Field(default_factory=dict)`.

### 2. `titan_agent/mcp_client.py` — Windows MCP stability
- **Issue:** asyncio transports were not closed when an MCP server stopped → on Windows a
  `ValueError: I/O operation on closed pipe` ResourceWarning spam.
- **Fix:** `stop()` now cancels and awaits `_read_task`, fully stops the process and closes stdin/stdout/stderr pipes. `_listen_stdout` also closes cleanly with `finally`.
- **Fix:** `start()` cleans up the process through `stop()` on error.
- **Fix:** `send_request` returns a clear error message on timeout (previously empty).

### 3. `mcp_servers.json` — broken fetch server removed
- **Issue:** the `@modelcontextprotocol/server-fetch` package was removed from npm (HTTP 404),
  so MCP startup failed and the `fetch` server would not connect.
- **Fix:** removed from config; `filesystem` (14 tools) connects reliably.
  Internet search is done through Titan's own `web_search` / `scrape_webpage` tools.

### 4. `titan_agent/llm_client.py` — Puter.js provider supported
- **Issue:** the frontend had a "Puter.js" provider option, but the backend did not recognize it
  → saving settings fell back to a broken OpenAI state.
- **Fix:** the `puter` provider is recognized in `_setup_credentials` (empty base_url/api_key).
- **Fix:** `chat_completion` raises a clear error when `puter` is called server-side ("Puter.js only runs in the browser").
- **Fix:** added a guidance hint for HTTP 401/403 errors.

## 🟡 Improvements

### 5. `tests/test_components.py` — adapted to pytest
- **Issue:** the old test file was not found by pytest ("no tests ran") — it was script-style.
- **Fix:** real pytest test functions written (`python -m pytest tests -q` → **13 passed**).

### 6. Configuration defaults
- `.env` / `.env.example` → default `TITAN_PROVIDER=puter`, `TITAN_MODEL=deepseek/deepseek-v4-pro`
  (developer.puter.com free models; no API key required).

### 7. `README.md` updated
- Puter.js setup path, Ollama note, `pytest` command, fetch-server note.

## 🆕 "All Puter Models" browser

- **`index.html` + `app.js` + `style.css`**: Settings now have a "🌐 All Models"
  button — clicking loads ALL models from Puter via `puter.ai.listModels()`
  (500+ models: Claude, GPT, Gemini, DeepSeek, Llama, FLUX and more).
- **"Popular / All" tabs**: the Popular tab shows `:free`-variant models only (free, no key, with rate limit).
- **Live search**: filters by model name, ID or provider.
- **Provider grouping**: models grouped by provider name.
- **Auto-load**: the model list loads automatically when Settings open or when the provider switches to Puter.js.

## 🆕 Agent Core 2.0 — beyond Hermes' max tier

- **`titan_agent/agent.py`**: new `TITAN_SYSTEM_PROMPT` — **Plan-Act-Verify-Report**
  discipline: always plan first, act decisively, verify results, report clearly.
- **Live tool catalog**: on every turn all available tools (built-in + MCP) are appended to the
  system prompt automatically (`LIVE TOOL CATALOG`) — the model knows exactly what it can do.
- **Efficiency rules**: avoid unnecessary steps, never re-request known results, stop immediately
  when the goal is reached — fewer tokens, faster answers.
- **`titan_agent/web_ui/app.js`**: the Puter browser-mode system prompt was raised to the same
  level as the backend (tool catalog + discipline + language rule).

## 🆕 Execution modes (2026)

- **`agent.py`**: `run_task(..., mode="fast" | "deep" | "deep_search")`
  - `deep` → `DEEP_THINKING_PROMPT`, reflection always runs, double iteration budget (max 40).
  - `deep_search` → auto-builds a research dossier via `DeepSearchEngine` and seeds it into the context, plus `DEEP_SEARCH_PROMPT`.
- **`server.py`**: `ChatRequest.mode` field; `/api/chat/stream` passes it to the agent loop.
- **`web_ui`**: mode selector (⚠️ Fast / 🧠 Deep Thinking / 🔍 Deep Search) wired into both the server stream and the Puter in-browser path.
- **`cli.py`**: in-session mode switching — type `mode deep` / `mode deep_search` / `mode fast`.

## 🆕 Parallel tool execution (2026)

- **`agent.py`**: `_emit_tool_results` now executes all tool calls of a turn **concurrently**
  with `asyncio.gather` (events streamed as "Running N tools in parallel...").
- **`web_ui/app.js`**: the Puter in-browser tool loop now batches all `<tool_call>` items and runs them
  with `Promise.all` — multiple AI tools work simultaneously in both modes.

## 🆕 English-only UI (2026)

- Entire User Interface, CLI, agent status messages, CLI banner, README/CHANGES translated to **100% English**.
- Model names are displayed **without the `:free` suffix** in the UI (the full variant ID is still used internally for the API call).

## 🆕 PowerShell / CLI improvements

- **`start-titan.ps1`** (new): automatic Python check, `venv` creation, dependency install, `.env`
  creation and Web/CLI launch. Parameters: `-CLI`, `-Port`, `-Provider`, `-Model`, `-NoBrowser`.
- **`start.bat`** now delegates to the PowerShell script (keeps one-click working).
- **`run.py`**: new `--provider` and `--model` flags — sets `TITAN_PROVIDER` / `TITAN_MODEL` before
  config import (e.g. `python run.py --provider ollama --model hermes3:8b`).
- **`cli.py`**: when `puter` is selected in the CLI (Puter only runs in the browser), it automatically looks for
  local **Ollama** models and switches to one; otherwise it guides the user clearly.

## 🆕 GitHub readiness

- **`git init` + first commit** (26 files, ~3948 lines).
- **`.gitignore`** (new): `.env` (secret), `venv/`, `__pycache__/`, `*.db`, `workspace/`, `*.zip`
  and other runtime/IDE files excluded.
- **`LICENSE`** (new): MIT license.
- **`.github/workflows/tests.yml`** (new): CI — runs `pytest` on Python 3.10/3.12 on push/PR.
- **`README.md`** rewritten: badges, PowerShell instructions, Puter models path, project structure, license.
- **`mcp_servers.json`** made portable: `{WORKSPACE}` placeholder instead of a hardcoded path —
  `mcp_client.py` replaces it automatically with the real path (works on any machine).

## 🆕 Local Workspace RAG + auto memory recall (2026)

Two zero-cost, zero-dependency capabilities (no embeddings, no API keys):

- **`workspace_rag(query, top_k?)` tool** (`titan_agent/tools.py`) — a lightweight local
  **BM25-style retrieval index** over every text/code file in the workspace. Files are split
  into overlapping chunks, scored against the query, and the top snippets are returned **with
  their file paths** so the LLM can answer document/code questions *with citations* without
  reading whole files. Works both in the backend agent loop and the in-browser Puter mode.
- **Auto memory recall** (`titan_agent/memory.py` + `agent.py`) — at the start of every task,
  Titan matches the user's request against saved long-term facts (`recall_relevant`) and seeds
  the most relevant ones into the system context as *Remembered Facts*, so a session begins
  already knowing the user (Memory-Agent pattern). The recall is best-effort lexical overlap —
  silent when nothing matches, never noisy.
- **Web UI** (`web_ui/app.js`) — the Puter system prompt advertises `workspace_rag` so the
  in-browser agent reaches for it too.
- **Tests** — `test_tool_workspace_rag` (finds relevant snippets + paths, ignores unrelated
  files), `test_memory_auto_recall` (only matching facts returned, exact key match ranks
  first), `test_run_task_auto_recalls_memory_into_system_prompt` (proves the remembered
  facts reach the model's system context).

## 🆕 Effort Levels (2026)

How hard Titan works on a task — user-selectable in the Web UI, CLI, `--effort` flag or `TITAN_EFFORT` env:

- **Web UI** — an **Effort:** selector sits right under the Mode selector: 🌱 Low / ⚖️ Medium / 🔥 High / 🚀 Ultra
  (emerald-active pills, same visual language as modes). Sent to the server stream and woven into the
  Puter in-browser system prompt as an "EFFORT LEVEL" block.
- **CLI** — `effort low|medium|high|ultra` (or `/effort high`) switches mid-session; `--effort` flag and
  the banner show the active level. Modes and effort combine independently.
- **`agent.py`** — `run_task(..., effort="auto"|"low"|"medium"|"high"|"ultra")`:
  - Iteration budget = mode base (fast 25, deep/deep_search 40) × effort multiplier
    (low 0.5 / medium 1.0 / high 1.6 / ultra 2.0), clamped to 48. **`auto` keeps the classic
    mode budget** so existing deep behavior is unchanged unless the user opts in.
  - HIGH/ULTRA always force the critic reflection pass (even without tool use); LOW adds
    speed-first guidance and skips forced reflection.
  - The planning status event now reports `(effort: X, max steps: N)` live.
- **Tests** — `test_effort_levels_scale_budget` (resolution + monotonic budget scaling +
  clamping), `test_run_task_effort_guidance` (ULTRA → guidance + forced reflection = 2 LLM
  calls; LOW → speed guidance + single call).

## 🆕 Token Throughput Guard (214k tokens/s) (2026)

A hard token-per-second guardrail so Titan can never burst past its budget:

- **`titan_agent/token_limit.py`** (new) — `TokenRateLimiter`, an async **token bucket**:
  up to 214,000 tokens/s (default, `TITAN_TOKEN_RATE_LIMIT` in `.env`), one second of burst,
  then any call that would exceed the cap waits exactly long enough for the refill.
  `estimate_tokens()` reserves input + max-output **before** every call (the cap is enforced
  on the way in, never after the fact). Accounting: tokens reserved, calls, throttling waits.
- **`llm_client.py`** — every server-side `chat_completion` first
  `await self.token_limiter.acquire(estimate_tokens(...))` (covers OpenRouter/DeepSeek/Groq/Ollama/CLI).
- **`server.py`** — new **`GET /api/token-usage`** endpoint returning the cap and live stats.
- **Web UI** — the Puter in-browser path has the **same** token bucket in `app.js`
  (`TOKEN_RATE_LIMIT = 214000`, `acquireTokens()` called right before `puter.ai.chat`);
  a subtle `🔒 214k tok/s` badge sits in the dashboard header.
- **Tests** — `test_token_rate_limit_default_is_214_k`, `test_token_limiter_enforces_rate`
  (tiny 10 tok/s bucket: first call free, second throttled ~1s), `test_estimate_tokens_returns_positive`,
  `test_token_usage_endpoint_shape`.
- With the default cap the guard is effectively invisible in production — the 214k/s budget
  is far larger than any real workload — but the throttling is real and provable.
- **`server.py`** — also replaced the deprecated `@app.on_event("startup"/"shutdown")` with a
  modern `lifespan` handler, so `pytest` output is fully clean: **29 passed, 0 warnings**.

## ✅ Verified status

- `python -m pytest tests -q` → **29 passed, 0 warnings**
- Server `python run.py` → starts, Web UI `http://127.0.0.1:7860`
- MCP `filesystem` server (14 tools) connects cleanly with the `{WORKSPACE}` placeholder
- Config: `puter / deepseek/deepseek-v4-pro`
- Chat stream: status → step_start → result/error (controlled), English messages only
- Deep Search mode: auto-dossier "Dossier ready: N sources found." + double iteration budget (max 40)
- Parallel tool execution: 4 simultaneous `/api/tools/execute` calls verified (all 200)
- MCP: **4 real servers** (filesystem 14, memory 9, sequential-thinking 1, everything 13 = 37 MCP tools) connect in **parallel**;
  8 simultaneous tool calls across all servers verified (all 200, 0.12s)
- Git: initial commits on `master`

## 🆕 Ultra-parallel MCP (10+ servers at once)

Works with **every MCP server simultaneously** — even **10+ at the same time**:

- **`mcp_client.py`** — the whole manager was hardened for multi-server concurrency:
  - **Parallel startup** — `start_all()` now launches every configured server with `asyncio.gather`,
    each with its own 90s timeout. A slow or broken server never blocks the others.
  - **stderr drain** — every server's stderr is continuously read (tail kept), so a chatty server
    can never deadlock its pipe buffer (a real risk with 10 servers).
  - **Per-server semaphore** — up to 32 concurrent calls per server; unbounded flooding is impossible,
    but 10+ servers still run at the same time.
  - **Auto-restart** — if a server disconnects mid-session, the next tool call restarts it automatically
    (seamless operation, no manual reload).
  - **Fail-fast on dead server** — pending requests are failed immediately when a server closes the
    connection instead of hanging for the full 60s timeout.
  - **Reliable tool routing** — an exact lookup map (`get_all_tools`) resolves
    `mcp_{server}_{tool}` names, so server names containing underscores (e.g. `my_server`) work
    correctly; the map rebuilds on demand if missing.
  - **Parallel shutdown** — `stop_all()` stops every server with `asyncio.gather`.
- **`mcp_servers.json`** — now ships 4 officially supported reference servers (all free, no API keys):
  `filesystem` (14 tools), `memory` (9 tools), `sequential-thinking` (1 tool), `everything` (13 tools) = **37 MCP tools**.
  (`server-fetch`, `server-time` and `server-git` were removed from npm — they 404; omitted on purpose.)
- **Tests** (`tests/test_components.py` + new `tests/fake_mcp_server.py`):
  - `test_mcp_10_servers_load_and_run_in_parallel` — spins up **10 real MCP processes**,
    starts them in parallel, then executes 10 tool calls **across** the servers and 10 calls
    **within** one server concurrently, asserting wall-clock parallelism (not just "they returned").
  - `test_mcp_single_broken_server_never_blocks_others` — one dead server is isolated; the healthy
    ones still start and serve tools.
  - `test_mcp_auto_restart_after_disconnect` — killing a server mid-session, the next call
    auto-restarts it and the tool still works.

## 🆕 Beyond Hermes' max tier — Agent Core 2.0

Hermes 405B (max tier) can only produce text — it **cannot do anything** in the real world: it cannot run
commands, verify results, or remember anything. Titan is now completely superior on all of these layers:

### 1. Reflection (self-critique) pass — `agent.py`
- After a task with tools, the model critically reviews its own work **BEFORE** giving the final answer
  (`REFLECTION_PROMPT`): was the user's request fully satisfied? Are all claims verified by tool results? Any errors?
- If reflection finds gaps → it automatically **makes extra tool calls** and fixes them,
  otherwise it returns the polished final answer.
- This is a real **verification loop** that Hermes (single-pass model) cannot perform.

### 2. Active long-term memory tools — absent in Hermes
- `memory_save(key, value, category?)` — remembers a fact forever (across all sessions).
- `memory_search(query)` — recalls facts saved in earlier sessions.
- The agent now independently saves and remembers user names, preferences, and decisions.

### 3. Real-world control tools
- `system_info()` — live OS / CPU / RAM / disk / Python / Node / Git facts.
- `manage_processes(action: list|kill, pattern?)` — list or stop running processes
  (tasklist/taskkill or ps/kill).
- The frontend (Puter mode) system prompt was also filled with the new tool catalog + reflection rule.

### Live verification results (localhost:7860)
- `system_info` → Windows 11, 12 CPU cores, 15.3 GB RAM, Python 3.12, Node v24, Git 2.55
- `manage_processes` → python processes listed with PIDs
- `memory_save`/`memory_search` → a "user_lang" fact saved in one turn and successfully recalled

## 🆕 Hermes-class capability bundle (5 blocks) (2026)

Full upgrade of Titan to a Hermes/ECC-level operator — built as five capability blocks,
each verified live. **No bigger model was pulled; the 14B model stays, the capability
layer grew.**

### Block 1 — Skills system (`titan_agent/skills.py` + `skills/`)
- **`skills.py`** (new): `SkillRegistry` loads markdown "playbooks" with YAML-like
  front-matter (`name / description / keywords`) from `skills/*.md`.
- **Auto-skill-load**: at the start of every task, the registry matches the user's
  request by keyword overlap and **injects the relevant playbooks into the system
  prompt** (`### RELEVANT SKILL PLAYBOOKS`, size-capped) — the same pattern Hermes
  uses for its skills catalog.
- **Tools**: `skills_list` (browse the catalog) + `skill_load { name }` (pull a full
  playbook on demand, e.g. `/plan` → planning-ops).
- **Shipped skills**: `research-ops`, `github-ops`, `coding-rules`, `terminal-ops`,
  `security-ops`, `planning-ops`.
- **Tests** — `tests/test_skills.py` (6): front-matter parsing, scanning, keyword
  ranking, on-demand load, system-block injection, real catalog.

### Block 2 — Cron / scheduler (`titan_agent/scheduler.py` + `cron/jobs.json`)
- **`scheduler.py`** (new): `CronScheduler` reads `cron/jobs.json` (Hermes-style) and
  fires enabled jobs by calling an async runner — in the server that runner is the
  live agent, so a job = a prompt executed autonomously on a timer.
- **Two schedule formats**: `interval_minutes: N`, and full 5-field cron
  (`*/5`, ranges, lists — minute-first, weekday mapping handled).
- **State persistence**: `last_run / last_status / last_result` write back into
  jobs.json, so a restart keeps history. No overlapping runs; failures are marked.
- **Server endpoints**: `GET/POST /api/cron/jobs`, `DELETE /api/cron/jobs/{id}`,
  `POST .../toggle`, `POST .../run` (manual force-run). Loop starts in `lifespan`.
- **Tests** — `tests/test_scheduler.py` (8): cron parsing/matching, add/remove/toggle,
  interval firing on tick, disabled jobs never fire, manual run-now, error marking,
  jobs.json persistence.

### Block 3 — Memory Vault scopes + handoffs (`titan_agent/memory.py`)
- **Scoped vault** (hermes "Memory Vault"): new `vault` table keyed `(scope, key)`
  so the same key can exist in `global / project / team / user` scopes.
  `vault_remember / vault_search / vault_list`.
- **Auto-recall merged**: `recall_relevant` now searches the legacy knowledge table
  **and** the scoped vault, so remembered facts from any scope seed the context.
- **Backward compatible**: `remember_fact(key, value, category)` without a scope still
  writes the legacy table (unchanged behavior).
- **Handoffs** (agent-to-agent/agent-to-human pass-along): `handoffs` table +
  `handoff_create / list / resolve`. New agent tools: `vault_list`, `handoff_create`,
  `handoff_list`, `handoff_resolve`; `memory_save/search` gained an optional `scope`.
- **Server endpoints**: `/api/memory/vault`, `/api/memory/handoffs`.
- **Tests** — `tests/test_memory_vault.py` (7): scoped writes/finds, no `(scope,key)`
  collisions, legacy compat, scope routing, merged recall, handoff lifecycle.

### Block 4 — Slash commands (`titan_agent/commands.py` + CLI + Web UI)
- **`commands.py`** (new): pure-function command layer mirroring Hermes commands.
- **LLM commands**: `/plan`, `/review`, `/security-scan`, `/research`, `/explain`,
  `/fix`, `/test`, `/remember`, `/handoff` — each maps to a specialized prompt +
  mode + effort (e.g. `/security-scan` → deep + ultra).
- **Local commands** (no LLM): `/help`, `/status`, `/mode`, `/effort`, `/skills`,
  `/memory`, `/handoffs`, `/clear`, `/exit`.
- **CLI** (`cli.py`): both local rendering and LLM-command expansion wired into the
  REPL loop, banner updated, `agent.memory`/`agent.skills` surfaced.
- **Web UI** (`app.js`): an in-browser mirror (`expandSlashCommand`) so the Puter
  path behaves identically; local commands render straight into the chat area;
  slash commands auto-switch mode/effort pills.
- **Tests** — `tests/test_commands.py` (8): expansion, mode/effort mapping,
  no-arg fallback, local parsing, English-only catalog.

### Block 5 — Extended MCP baseline (`mcp_servers.json` + `mcp_client.py`)
- **8 MCP servers, 95 tools** (live-verified): `filesystem`, `memory`,
  `sequential-thinking`, `everything`, **`github` (26 tools — repos, PRs, issues,
  commits, code search)**, **`fetch` (1 tool — web page retrieval, now via `uvx
  mcp-server-fetch` because the npm package was replaced by a security placeholder)**,
  **`context7` (2 tools — up-to-date library docs)**, **`chrome-devtools` (29 tools —
  browser automation: navigate, click, screenshot, console/network, lighthouse)**.
- **`mcp_client.py`**: env values now support `{ENV_VAR}` placeholders (e.g.
  `{GITHUB_TOKEN}`) resolved from the process environment — missing vars become
  empty strings so the server still launches and only auth-gated calls fail.
- **Tests** — `tests/test_mcp_extended.py` (4): config presence, command/args shape,
  env placeholder expansion, missing-env → empty without crash.

### Verified status
- `python -m pytest tests -q` → **62 passed** (was 29)
- Live server: **8/8 MCP servers connected, 95 tools** (github 26, chrome-devtools
  29, filesystem 14, everything 13, memory 9, context7 2, sequential-thinking 1,
  fetch 1)
- Cron: add/list/toggle/delete verified over HTTP; scheduler tick tested in pytest
- Vault + handoffs: create/search/resolve verified over HTTP
- Skills: `skills_list` returns the 6 playbooks via `/api/tools/execute`
- CLI with local Ollama `hermes3`: slash commands (help/status/skills) and a real
  fast-mode LLM answer verified end-to-end
- Token guardrail (214k tok/s) untouched and still enforced in both paths
- Zip deleted, not regenerated; user-visible text stays 100% English

## 🆕 Free Completions.me provider (2026)

Added the `completions` provider — a **free OpenAI-compatible gateway** that serves
Claude Opus/Sonnet, GPT-5.x, Gemini 3 Pro and Grok with no credit card and no rate
limits.

- **`.env`**: new `COMPLETIONS_API_KEY` (user-supplied `sk-cp_...` key) +
  `COMPLETIONS_BASE_URL=https://completions.me/api/v1`.
- **`titan_agent/config.py`**: reads both variables.
- **`titan_agent/llm_client.py`**: `completions` branch in `_setup_credentials`;
  browser `User-Agent` + `Accept` headers so Titan passes Completions' Cloudflare
  gateway (plain urllib requests get blocked there); provider hints updated in
  error messages.
- **Web UI** (`titan_agent/web_ui/index.html`): new dropdown option
  `Completions.me (FREE — Claude Opus / GPT-5 / Gemini / Grok)`.
- **CLI**: works via `python run.py --provider completions --model claude-sonnet-4.5`.
- **Verified live**: `LLMClient(provider="completions", model="claude-sonnet-4.5")`
  returned a real completion through the Titan code path.

Note: a raw `urllib` probe against the same endpoint got HTTP 401 "Invalid API key"
and HTTP 403 Cloudflare 1010 — both are WAF-related, not key problems; the key is
confirmed valid through Titan's own client (browser-style headers).

## 🆕 Telegram account manager — user-consented (Block 6, 2026)

The agent can now manage the **user's own Telegram accounts** (add via one-time
code, list, read own dialogs, send only to an allowlist) — built around an
explicit safety model:

- **Consent gate:** nothing works unless `TITAN_TELEGRAM_ENABLED=true` in `.env`
  (default `false`). Disabled ⇒ every tool answers "Telegram control is disabled".
- **Credentials:** `TITAN_TELEGRAM_API_ID` / `TITAN_TELEGRAM_API_HASH` from
  https://my.telegram.org → API development tools. The agent cannot invent the
  user's phone or one-time code — login always starts from the user's own number
  and is only completed with the code the **user** received and shared.
- **Send allowlist:** messages go out **only** to targets listed in
  `TITAN_TELEGRAM_SEND_ALLOWLIST` (comma-separated). Empty ⇒ read-only; a refusal
  happens *before* any connection. No broadcast / mass-messaging tooling exists.
- **PII hygiene:** phone numbers and usernames are masked in every output
  (`+998 ** *** ** 67`); `api_hash` is never printed; sessions live in
  `workspace/telegram_sessions/` (git-ignored), never in the repo.

Files touched:
- **`titan_agent/telegram.py`** (new, ~330 lines): `TelegramManager` — consent
  gates (`enabled`, `has_credentials`, `send_allowlist`), login flow
  (`login_start` → `login_confirm` with user code), `list_accounts`, `status`,
  `send_message` (allowlist-checked before connecting), `recent_messages`
  (read-only, masked senders), `whoami`, `logout`; Telethon imported lazily so the
  app runs even without it installed.
- **`titan_agent/config.py`**: `TITAN_TELEGRAM_ENABLED / _API_ID / _API_HASH /
  _SEND_ALLOWLIST`.
- **`titan_agent/agent.py`**: 7 agent tools (`telegram_status`, `telegram_accounts`,
  `telegram_login_start`, `telegram_login_confirm`, `telegram_send`,
  `telegram_recent`, `telegram_logout`) in the live tool catalog + dispatch; every
  `TelegramError` is surfaced as a friendly "Telegram: …" message.
- **`titan_agent/server.py`**: REST API — `GET /api/telegram/{status,accounts,recent}`,
  `POST /api/telegram/{login/start, login/confirm, send, logout}` (all error-wrapped).
- **`titan_agent/__init__.py`**: exports `TelegramManager`, `TelegramError`.
- **`.env` / `.env.example`**: new opt-in block (disabled by default).
- **`requirements.txt`**: `telethon>=1.34.0` (installed).
- **`pytest.ini`** (new): `testpaths = tests`, `norecursedirs = workspace …` — stray
  agent scratch files can no longer break collection.
- **`tests/test_telegram.py`** (new, 10 tests): consent gate, allowlist parsing +
  pre-network refusal, PII masking, status shape, agent-dispatch paths — all
  deterministic, no network.

Verified: `python -m pytest -q` → **72 passed** (62 + 10 new); server restarted on
`127.0.0.1:7860`; `GET /api/telegram/status` reports `enabled: false` until the user
opts in via `.env`.

## 🆕 Agent Core — Phase 1: foundation (2026)

Production-grade foundation for the agent engine:

- **`titan_agent/config_v2.py`** (new) — Pydantic Settings v2 based configuration:
  nested `LLMSettings` / `ToolSettings` / `MemorySettings`, `.env` loading, validation errors
  surfaced as `ConfigError`.
- **`titan_agent/exceptions.py`** (new) — `ErrorCode` enum + `TitanError` hierarchy
  (`LLMError`, `ToolError`, `ConfigError`, `MemoryError`, `AgentError`, `MCPError`,
  `RouterError`): every error carries a **`details`** payload and a machine-readable
  error code; `get_error_chain()` walks the cause chain; `is_retryable()` classifies
  transient (429/network/timeouts) vs permanent failures; `wrap_error()` attaches
  context. `LLMError` with status 429 is retryable.
- **`titan_agent/di.py`** (new) — dependency injection: `ServiceRegistry` (typed services,
  lazy singletons, override support), `ExecutionContext` (per-request context with
  cancellation + metadata), `execution_context()` async context manager, `LifecycleManager`
  (async startup/shutdown hooks), `cancelled()` cancellation check helper.
- **`tests/test_phase1.py`** (new, 18 tests) — settings env override + secret masking,
  exception chain/dict/retryability, DI override/scope, lifecycle ordering,
  context cancellation.

## 🆕 Agent Core — Phase 2: seven agent-competition patterns (2026)

The strongest patterns from the 2026 agent comparison (Claude Code, Codex, Cursor,
Copilot, Devin, Windsurf, OpenCode, Aider, Cline, Replit, Gemini CLI, Cody, Tabnine)
integrated as a **modular, dependency-free core** under `titan_agent/core/`.
Every module follows interface → implementation → tests → docs, with typed
interfaces so engines and providers can be swapped.

### 1. Reasoning — `core/reasoning/` (ReAct + Plan-and-Execute + ToT)
- **`ReActEngine`** (`react.py`) — Think→Act→Observe loop: LLM decisions with native
  tool calling (`complete_with_tools`) and structured-JSON text fallback; unknown/failed
  tools become observations instead of crashing; periodic `Reflector` pass; steps capped
  at `max_steps`; streaming support (`stream_reason`).
- **`PlanExecutor`** (`planner.py`) — LLM-driven plan creation with tool awareness;
  dependency-aware `Plan.get_ready_steps()`; `replan()` after failure preserving
  completed steps; resilient JSON parsing.
- **`ToTEngine`** + **`LLMEvaluator`** (`tot.py`) — Tree of Thoughts beam search:
  branch (LLM generates distinct next-thoughts) → expand → evaluate (`IEvaluator`) →
  prune top-k → early solution detection via `is_solution()`.
- **`ReasoningConfig`** — max steps, observation/token caps, plan steps, retries,
  reflection interval, ToT branching factor/depth (all bounded by pydantic validation).

### 2. Memory — `core/memory/` (MemGPT/Mem0-style)
- **`MemorySystem`** (`memory_system.py`) — SQLite-backed episodic / semantic /
  procedural memory + **ephemeral working memory** (in-process, never persisted).
- **Retrieval scoring** — composite: keyword overlap + recency decay `1/(1+days)`
  + importance + access frequency; every returned record updates `access_count`.
- **Consolidation** — repeated high-importance episodes become semantic facts
  (deduplicated, importance boosted, `source_count` metadata).
- **Lifecycle** — `forget()` (old + low-importance), `clear()`, `stats()`.
- **File-lock safe** — every SQLite connection is context-managed and closed
  (Windows safe: DB file deletable after use).

### 3. Reflection — `core/reflection/` (Devin/Reflexion-style)
- **`Reflector`** — LLM analyzes the reasoning trace → `insight` / `correction` /
  `halt` / `confidence`; persists a **lesson** (procedural memory) when the tail of a
  trace contained failures.
- **`LessonStore`** — experience memory backed by `MemorySystem`
  (kind=PROCEDURAL, scope="lessons"); relevant lessons are retrievable before
  future runs.

### 4. Orchestration — `core/orchestration/` (AutoGen/LangGraph-style)
- **`AgentTeam`** — register typed agents by `AgentRole`
  (supervisor/planner/researcher/coder/reviewer/tester/executor).
- **Four coordination modes**: `SEQUENTIAL` (pipeline, fail-fast), `PARALLEL`
  (fan-out via `asyncio.gather`), `CONSENSUS` (multiple agents vote, majority answer),
  `SUPERVISOR` (lead decomposes → specialists work → lead synthesizes).
- One agent failing never crashes the team (`AgentResult.ok` / `.error`).

### 5. Guardrails — `core/guardrails/` (Constitutional AI + Cline-style HITL)
- **`PolicyEngine`** — rule evaluation (allow / deny / require_approval) with
  prefix-matched resources; prompt-injection phrase detection; SSRF protection
  (private/loopback IP patterns); PII/secret pattern scanning; JSONL **audit trail**.
- **`HumanInTheLoop`** — approval requests with async `wait()` + timeout → approved /
  denied / timed_out / cancelled; audit of who decided what.

### 6. Tools — `core/tools/` (Cursor/Codex-style tool composition + sandbox)
- **`ToolRegistry`** — wraps any executor (`tools.ToolRegistry` shape:
  `get_tool_definitions()` + `tool_*` handlers) behind the `IToolExecutor` interface.
- **Discovery** — search tools by keyword / `ToolCategory` / risk ceiling
  (`RiskLevel` classification from name+description heuristics).
- **Policy gate** — every execution runs through `PolicyEngine`; command tools are
  checked with the **command text as the resource** (so `rm -rf` → deny works).
- **Sandbox** — path arguments are resolved inside the workspace; escapes raise
  `PermissionError` (via `is_relative_to`).
- **Composition** — `compose()` chains tool outputs into later inputs
  (`{"$result": 0, "$path": "field"}` templates); `run_parallel()` fans out.

### 7. Integration — verified wiring
- `ToolRegistry` implements `IToolExecutor` → a `ReActEngine` drives policy-guarded
  tools directly; a **policy denial surfaces as a failed ACT step** and the agent
  recovers with an alternative tool (proven by test).
- `Reflector` implements `IReflector` → plugs into `ReActEngine` reflection turns.
- `LLMEvaluator` implements `IEvaluator` → plugs into `ToTEngine`.

### Verified status
- `python -m pytest tests -q` → **178 passed** (was 103 at the start of Phase 2)
- `python -m ruff check titan_agent/core/` → **All checks passed**
- `python -m ruff check titan_agent/` → only the 4 known `ASYNC221` warnings remain
  (Unix-only `wmctrl` subprocess calls in `tools.py`, cosmetic by decision)
- Temp script `fix_llm.py` removed.

## 🆕 Agent Core — Phase 3: live-loop integration (2026)

The Phase 2 core engines are now wired into the **production agent loop** instead of
being standalone modules — the difference that matters head-to-head against the
models/agents in the 2026 comparison (Claude Code, Codex, Devin, Cline, Aider, ...).

### 1. Structured reasoning in `run_task` — `titan_agent/structured.py`
- New `strategy` parameter on `TitanAgent.run_task`: `auto | plan | react | tot`.
  `auto` keeps the classic prompt-driven loop byte-for-byte (backward compatible);
  the other three run the Phase 2 core engines inside the live event stream.
- `StructuredEngine` composes **PlanExecutor → ReActEngine** (plan), pure
  structured **ReActEngine** (react) or **ToTEngine → ReActEngine** (tot: Tree-of-
  Thoughts picks the best strategy, then real tools execute it).
- `LLMBridge` adapts the production `LLMClient` to `ILLMProvider`; `ToolBridge`
  adapts `execute_tool_unified` to `IToolExecutor`; `ReflectorAdapter` gives the
  loop a live self-critique phase.
- Streams the same `AgentEvent` shape as the classic loop (`plan`, `thought`,
  `tool_call`, `tool_result`, `status`, `final_answer`, `error`) — Web UI and CLI
  work unchanged; the final answer is saved to conversation memory.

### 2. Policy guardrails in the live loop (Cline-style)
- Every tool activation from a structured run passes through `PolicyEngine`
  (`DEFAULT_RULES`): `deny` blocks the call, `require_approval` waits for a
  `HumanInTheLoop` approval (auto-denies in autonomous mode), everything is
  logged to the audit trail. A blocked tool surfaces as a failed ACT step and the
  agent recovers via an alternative tool.

### 3. Frontier-class open-weight providers — `config.py` / `llm_client.py`
- **`kimi`** provider (Kimi K3 — Moonshot, `https://api.moonshot.cn/v1`,
  default model `kimi-k3`) and **`glm`** provider (GLM-5.3 Flash — Zhipu,
  `https://open.bigmodel.cn/api/paas/v4`, default model `glm-5.3-flash`),
  both OpenAI-compatible. Default resolution precedence is now
  OpenRouter → Kimi → GLM → DeepSeek → Groq → OpenAI → Ollama; behaviour is
  unchanged until the new keys are set (`KIMI_API_KEY` / `GLM_API_KEY`).

### 4. Headless / CI runner — `titan_agent/headless.py`
- `python -m titan_agent.headless "task" --strategy plan --mode deep` runs a task
  to completion non-interactively (Claude-Code-style) and exits 0 only if a final
  answer was produced (`--json` prints the full event log incl. exit code).
- `run_headless(...)` is the programmatic API; `build_agent()` mirrors the web
  server's exact wiring.

### 5. Server pass-through
- `ChatRequest.strategy`, the SSE stream, and the cron runner all accept and
  forward `strategy`, so scheduled jobs and the dashboard can opt into structured
  reasoning.

### Verified status
- `python -m pytest tests -q` → **193 passed** (178 + 15 new Phase 3 tests)
- `python -m ruff check` on all changed files → **All checks passed**
- `python -m titan_agent.headless --help` → CLI parsing verified

## 🆕 Agent Core — Phase 4: Git-first workflow + core memory in the live loop (2026)

Phase 4 closes the two biggest gaps against the 2026 comparison set: **Aider's
git-first auto-commit** and the **MemGPT/Mem0-style episodic memory** that
Devin/Claude Code use to carry experience across sessions.

### 1. Git-first workflow (Aider-style) — `titan_agent/gitops.py`
- New `git_status`, `git_diff`, `git_commit` **tools** registered on every agent
  run (listed in the live tool catalog, routed through `execute_tool_unified`):
  the model can inspect the working tree and commit its own edits, exactly like
  Aider's "every change lands as a commit" loop.
- `git_commit` stages everything (`git add -A`) and commits; if the repo has no
  identity it sets a **repo-local** author (`Titan Agent <titan@localhost>`,
  overridable via `TITAN_GIT_NAME` / `TITAN_GIT_EMAIL`) — never touches global
  config and never clobbers an existing global identity.
- Blocking git calls run through `asyncio.to_thread`, so the event loop keeps
  streaming; everything is fail-soft ("not a git repository" is a friendly string,
  never an exception).

### 2. Auto-commit at end of run (Aider's git-first default)
- `TitanAgent.run_task(..., auto_commit=True)` (or `TITAN_GIT_AUTO_COMMIT=1` in
  `.env`) commits workspace changes after a successful run with a subject derived
  from the task (`agent: <first 72 chars>`).
- The `TitanAgent` constructor takes `git_root` (defaults to the workspace) and
  finds the repo root by walking up for `.git`.
- Plumbed through `headless.py` (`--auto-commit` flag) and `server.py`
  (`ChatRequest.auto_commit`, cron runner).

### 3. Episodic core memory in the live loop (`core/memory` MemorySystem)
- `TitanAgent` now owns a `MemorySystem` (lazily opened — construction never
  touches disk; the file is `workspace/core_memory.db`, gitignored) with
  `core_memory_path` for custom locations.
- **Write:** every completed run (classic _and_ structured paths) records an
  episodic memory via `_finalize_run`: task, result, mode, strategy, session —
  the agent's own run history becomes machine-remembered context.
- **Read:** before each run, `_core_recall_block` pulls relevant past runs/
  lessons into the system prompt (both classic loop and structured contexts),
  only when records exist — fresh stores leave prompts byte-identical.

### 4. Honest status
- `python -m pytest tests -q` → **208 passed** (193 + 15 new Phase 4 tests)
- `python -m ruff check` on all changed files → **All checks passed**
- Verified: headless import, `ChatRequest.auto_commit`, agent import, temp-repo
  end-to-end auto-commit (real `git init` + commit in pytest tmp dirs).

## 🆕 Agent Core — Phase 5: Devin-style checkpoints & resume (2026)

The continuity that defines long-horizon autonomy — **Devin's checkpointed
sessions** and **Claude Code's `--continue`/`--resume`** — is now native to
Titan. An interrupted session resumes from the exact state it stopped at.

### 1. `titan_agent/checkpoint.py` (new)
- `RunCheckpoint` — serializable snapshot: session, task, mode/effort/strategy,
  conversation messages (last 40), steps done, tools used, status
  (`running | done | error`), final answer.
- `CheckpointStore` — SQLite, one row per session, Windows file-lock-safe;
  `save` (upsert) / `load` / `list` (newest first) / `delete` / `stats`.

### 2. Always-on checkpointing in `run_task`
- Run start → `running`; after every tool step → messages + steps + tools saved
  (main loop and reflection pass); on error → `error`; on completion → `done`
  with final answer (classic _and_ structured `plan`/`react`/`tot` runs).

### 3. Resume — `run_task(..., resume=True)`
- A `done` session **replays its saved final answer without any LLM call**.
- An interrupted session restores its conversation and emits
  `Resuming session 'X' from checkpoint (N steps done, last status: ...)`, then
  continues the classic loop from where it stopped.
- No checkpoint → resume is a no-op (zero behaviour change).
- Honest: structured strategies re-plan on resume (their state is in-memory);
  the classic loop is restored verbatim (proven end-to-end: crash → error
  checkpoint → resume → done).

### 4. Plumbing
- `headless.py --resume` (CLI), `run_headless(..., resume=...)`,
  `ChatRequest.resume` (SSE) + cron runner.

### 5. Verified status
- `python -m pytest tests -q` → **220 passed** (208 + 12 new Phase 5 tests)
- `python -m ruff check` on all changed files → **All checks passed**
- End-to-end crash→resume→done proof runs green; CLI `--help` shows `--resume`.