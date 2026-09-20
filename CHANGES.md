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

## ✅ Verified status

- `python -m pytest tests -q` → **17 passed**
- Server `python run.py` → starts, Web UI `http://127.0.0.1:7860`
- MCP `filesystem` server (14 tools) connects cleanly with the `{WORKSPACE}` placeholder
- Config: `puter / deepseek/deepseek-v4-pro`
- Chat stream: status → step_start → result/error (controlled), English messages only
- Deep Search mode: auto-dossier "Dossier ready: N sources found." + double iteration budget (max 40)
- Parallel tool execution: 4 simultaneous `/api/tools/execute` calls verified (all 200)
- Git: initial commits on `master`

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
- `memory_save`/`memory_search` → "user_lang = O'zbek" saved and found