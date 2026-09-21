# ⚡ TITAN AGENT — Autonomous AI System, Far Beyond Hermes 3

> **Titan Agent** — an autonomous **Agentic AI Platform** that combines Agent Core 2.0 discipline,
> MCP (Model Context Protocol) integration, web research, coding, and OS control into one engine
> engineered to outperform Nous Research Hermes 3, DeepSeek-R1 and frontier-tier agents.

It does not just write text — it thinks autonomously, runs commands and programs on your computer,
searches the web live, and connects to any application or database through **Model Context Protocol (MCP)**.

| CI Status | License | Python |
|---|---|---|
| [![CI - Tests](https://github.com/YOUR_USERNAME/titan-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/YOUR_USERNAME/titan-agent/actions) | MIT | 3.10+ |

---

## 🚀 Key Advantages (Why it beats Hermes 3)

1. **Multi-Model & Flexible (Multi-LLM Routing)**:
   - **🚀 OmniRoute (default)** — self-hosted AI gateway (`localhost:20128`) with six `auto*` models that route each
     request to the best available provider/model automatically (`auto`, `auto/coding`, `auto/fast`, `auto/smart`,
     `auto/offline`, `auto/cheap`). One key, no per-provider fallback logic.
   - **Puter.js — 500+ models** (no key, runs directly in the browser): DeepSeek V4 Pro, Claude, GPT-4o, Llama and more
   - DeepSeek V4 Pro / Flash, Claude 3.7/3.5 Sonnet, GPT-4o / mini, Gemini 2.0 Flash
   - OpenAI GPT-4o / Claude 3.7 Sonnet (API keys optional)
   - Local **Ollama** (fully offline and private)
2. **🔌 Model Context Protocol (MCP) Integration**:
   - Connect GitHub, SQLite, PostgreSQL, Filesystem, Slack, Brave Search and any other MCP server via `mcp_servers.json`!
3. **🛠️ Powerful Built-in Tools**:
   - **PowerShell / Terminal commands**: full computer control.
   - **Filesystem**: read, create, edit (regex replace).
   - **📚 Local Workspace RAG**: `workspace_rag(query)` — zero-dependency BM25-style retrieval over ALL workspace
     files (docs, notes, code). Returns the most relevant snippets **with file paths** so answers come with citations,
     no embeddings or API keys needed.
   - **Live Web Search**: DuckDuckGo — fresh data, no key.
   - **Python Sandbox**: complex calculations and scripts in an isolated process.
   - **Deep Search**: multi-source research dossier.
   - **Deep Coder**: full software engineering cycle (write files, syntax check, run tests).
   - **Launch applications**: run Windows apps.
   - **System Info**: live OS / CPU / RAM / disk / Python / Node / Git facts.
   - **Process Manager**: list or kill running OS processes.
   - **🚑 Self-healing**: `self_heal` auto-installs missing Python modules and retries failed commands.
   - **🌐 Real-world actions**: `download_file` (SSRF-guarded), local `start_http_server`,
     `take_screenshot`, and `self_update` (git pull + pip install + tests).
   - **📋 Autonomous task queue + daemon**: `task_enqueue` / `task_list` / `task_stats` / `task_cancel`,
     run by `python -m titan_agent.daemon` — jobs processed with priorities, scheduling and retries,
     with **no human at the keyboard**.
   - **👥 Deep subagents**: `subagent_delegate` / `subagent_team` fan work out to independent child
     agents (fresh sessions / checkpoints), in parallel.
4. **🧠 Long-term Memory (SQLite)**:
   - Saves conversations and learned facts to SQLite and remembers them in future sessions (`memory_save` / `memory_search`).
   - **Auto recall**: every new task starts with the most relevant remembered facts already in context — the agent
     begins each session knowing your name, preferences and past decisions (Memory-Agent pattern).
5. **💻 Two Friendly Interfaces**:
   - **Web Dashboard**: modern dark cyberpunk glassmorphic control panel (reasoning display, tool animations, file manager, model browser).
   - **Terminal CLI**: Rich-based console.
6. **⚡ Agent Core 2.0 — beyond Hermes' max tier**:
   - **Reflection pass**: after every real task Titan critically reviews its own work, fixes errors and returns a polished answer (Hermes has no such loop).
   - **Active memory tools**: `memory_save` / `memory_search` — facts remembered across all sessions.
   - **Real-world control**: `system_info` and `manage_processes`.
7. **🎛️ Three Execution Modes**:
   - **⚡ Fast** — quick, efficient single-pass tasks.
   - **🧠 Deep Thinking** — extended reasoning, edge-case analysis, stricter verification, double iteration budget.
   - **🔍 Deep Search** — automatic multi-source research dossier seeded before the answer, plus research-first instructions.
8. **🌡️ Effort Levels** (`/effort`, `--effort`):
   - **🌱 Low** — speed first: minimal tool calls, direct concise answers, half the iteration budget.
   - **⚖️ Medium** — balanced default (budget ×1.0).
   - **🔥 High** — like a careful expert: decompose, verify every step (budget ×1.6, reflection always on).
   - **🚀 Ultra** — maximum thoroughness: exhaustive edge-case coverage, every claim verified (budget ×2.0, reflection always on).
   - `auto` (default) — derives from the mode: deep/deep_search automatically run at High rigor.
9. **🚀 Parallel Tool Execution**:
   - Multiple independent AI tools run **simultaneously** (batch tool calls) — from the agent loop and from the Puter in-browser path.
10. **🔒 Token Throughput Guard (214k/s)**:
    - A hard token-bucket guardrail: the agent can **never exceed 214,000 tokens/second**, no matter how many
      providers, parallel tool turns or long streams are running (default; override with `TITAN_TOKEN_RATE_LIMIT`).
    - Enforced on every server-side LLM call (`llm_client`) **and** on the Puter browser path (`app.js` token bucket).
    - Live stats endpoint: `GET /api/token-usage` (cap, tokens reserved, throttling waits) + a small `🔒 214k tok/s` badge in the dashboard header.

---

## 🚀 Quick Start

### Method 1: Windows — `start.bat` (one click)
Double-click `start.bat` and choose Web or CLI mode. The script auto-sets up `venv`, dependencies and `.env`.

### Method 2: PowerShell (recommended)
```powershell
# Web Dashboard (default):
.\start-titan.ps1

# Terminal CLI mode:
.\start-titan.ps1 -CLI

# Different port:
.\start-titan.ps1 -Port 8000

# Specific provider/model:
.\start-titan.ps1 -Provider ollama -Model hermes3:8b
```

### Method 3: Manual
```bash
# Launch Web Dashboard:
python run.py

# Or Terminal CLI mode:
python run.py --cli

# Temporarily switch provider/model:
python run.py --provider ollama --model hermes3:8b
python run.py --mode deep_search --effort ultra   # CLI: heavy research run
```

The web dashboard opens automatically in your browser at `http://127.0.0.1:7860`.

> 💡 **No API key required:** In the Web Dashboard open Settings (⚙️) and keep the **Puter.js** provider —
> click **"🌐 All Models"** to browse every available model and pick one (DeepSeek V4 Pro / Claude / GPT-4o etc.).
> Everything runs directly in your browser, no API key needed. Or use local **Ollama**.

---

## ⚙️ Settings & API Keys

Set the provider from the settings button in the top-right corner of the web interface, or in the `.env` file.

**First launch — create `.env`:**
```bash
copy .env.example .env
```

```env
# Puter.js — browser-side, no key:
TITAN_PROVIDER=puter
TITAN_MODEL=deepseek/deepseek-v4-pro

# Or a keyed provider:
TITAN_PROVIDER=deepseek
TITAN_MODEL=deepseek-chat
DEEPSEEK_API_KEY=your_key_here
```

### Using local Ollama:
1. Start Ollama on your computer: `ollama run hermes3` or `ollama run qwen2.5-coder`
2. Switch the provider to **Ollama** in Settings — no API key required!

> ⚠️ **Note:** Puter.js only works in the **browser (Web Dashboard)** — it runs inside the webpage that loads the
> `puter.ai` SDK. In the CLI, if Puter is selected, Titan automatically falls back to Ollama, otherwise it guides the user.

---

## 🔌 Adding MCP Servers

Add any MCP server to `mcp_servers.json`. `{WORKSPACE}` and `{BASE_DIR}` placeholders are replaced
automatically with real paths — so the configuration is portable. Titan Agent starts **all configured
servers in parallel**, and handles even **10+ servers at once** (each with its own timeout, stderr
drain, per-server concurrency cap and automatic restart if a server drops).

Ships with 4 officially supported reference servers (free, no API keys — 37 MCP tools total):
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "{WORKSPACE}"]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    },
    "everything": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-everything"]
    }
  }
}
```
When Titan Agent starts, it auto-detects all tools of these servers and adds them to its reasoning loop!
One broken server never blocks the others — it is skipped and the healthy servers keep working.

> 🔎 **Note:** Titan has its own `web_search` and `scrape_webpage` tools for internet data — a separate MCP
> fetch server is not needed (the old `@modelcontextprotocol/server-fetch` package was removed from npm,
> just like `server-time` and `server-git`).

---

## 🧪 Tests

```bash
python -m pytest tests -q
```

GitHub Actions CI (`tests.yml`) automatically runs tests on Python 3.10/3.12 on `push` and `pull_request`.

---

## 🗂️ Project Structure

```
titan-agent/
├── run.py                    # Main entry point (Web/CLI)
├── cli.py                    # Terminal CLI mode (Rich)
├── start-titan.ps1           # PowerShell launcher script
├── start.bat                 # Windows one-click launcher
├── requirements.txt
├── mcp_servers.json          # MCP server configuration
├── .env.example              # Settings template (copy to .env)
├── tests/                    # pytest tests
├── titan_agent/
│   ├── agent.py              # TitanAgent — the core agentic loop (Plan-Act-Verify-Reflect) + modes + memory tools
│   ├── llm_client.py         # Multi-provider LLM client (puter/openrouter/groq/deepseek/ollama/lmstudio/openai)
│   ├── tools.py              # Built-in tools (execute_command, web_search, workspace_rag, deep_search, deep_coder, system_info, manage_processes...)
│   ├── mcp_client.py         # Model Context Protocol connection manager
│   ├── memory.py             # SQLite long-term memory
│   ├── token_limit.py        # Token throughput guardrail (214k tokens/s token bucket)
│   ├── deep_search.py        # DeepSearchEngine — multi-angle research dossier
│   ├── deep_coder.py         # DeepCoderEngine — full software engineering cycle
│   ├── config.py             # Settings from .env
│   └── web_ui/               # Web Dashboard (index.html, app.js, style.css)
└── workspace/                # Agent working directory (gitignored)
```

---

## 📜 License

MIT License — see `LICENSE` for details.

---

## 🤝 Contributing

1. Fork and clone
2. Create a new branch: `git checkout -b feature/x`
3. Make changes and run tests: `python -m pytest tests -q`
4. Open a Pull Request

## ⭐ Support

If you like this project — give it a ⭐! For questions, suggestions and issues use GitHub Issues.