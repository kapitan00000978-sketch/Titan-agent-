# TITAN AGENT — Changelog

All fixes and improvements made during the completion effort of this project.

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