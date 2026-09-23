# ⚡ TITAN AGENT — Autonomous Cognitive AI Operating System (Genesis Edition)

[![CI - Test Suite](https://img.shields.io/badge/Test%20Suite-600%20Passed%20%7C%200%20Failures-brightgreen.svg)](https://github.com/kapitan00000978-sketch/Titan-agent-)
[![Python Version](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Architecture](https://img.shields.io/badge/Architecture-Genesis%20Levels%201--10-purple.svg)](docs/titan-agent-master-architecture.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Titan Agent** is an enterprise-grade **Autonomous Hierarchical Cognitive AI Operating System** built on the Genesis Architecture (Levels 1–10). Unlike single-prompt bots or sequential ReAct loops, Titan Agent functions like an autonomous tech enterprise: **CEO Meta-Orchestrator → 4 Department Leads → 27 Worker Specialists → Directed Acyclic Graph (DAG) Parallel Execution → Zero-Loss Sandbox Rollback → Longitudinal Drift Detection → Autonomous Self-Improvement Loop**.

---

## 🏛️ Genesis Cognitive Architecture (Levels 1 – 10)

```
========================================================================================
LEVEL 1 — META-ORCHESTRATOR (Chief Executive Agent)
  ├── Global Goal Memory (Maintains multi-session project roadmap & long-term objectives)
  ├── Resource & Token Budget Controller (Manages token consumption & USD spend)
  └── Multi-Agent Conflict Resolver (Resolves departmental priorities and constraints)
========================================================================================
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
LEVEL 2 — 4 DEPARTMENT TEAM LEADS
  ├── EngineeringLead (CTO)           : System architecture, code synthesis, API schemas
  ├── ResearchLead (Chief Scientist) : Multi-hop internet research, doc audits, vector RAG
  ├── OperationsLead (DevOps / SRE)  : Terminal actions, Docker sandboxes, Git migrations
  └── QualitySecurityLead (Audit/QA) : AST security scanning, test suites, zero-loss rollback
========================================================================================
                                     │
         ┌───────────────────────────┴───────────────────────────┐
         ▼                                                       ▼
LEVEL 3 — 27 SPECIALIST WORKER ROLES
  ├── Backend Specialist              ├── Database Specialist         ├── Security Auditor
  ├── Frontend Specialist             ├── Refactoring Specialist      ├── Performance Engineer
  ├── Vector RAG Specialist           ├── Test Engineer               ├── Browser Automation Lead
  └── (18 Additional Specialized Roles dispatched dynamically per task context)
========================================================================================
                                     │
LEVEL 4 TO 10 — COGNITIVE SUBSYSTEMS & REASONING RUNTIMES
  ├── Level 4: Directed Acyclic Graph (DAG) Task Planner & Wave-Based Parallel Executor
  ├── Level 5: Dual Reasoning Loops: Reflexion Engine & Multi-Agent Debate Arena
  ├── Level 6: Causal Knowledge Graph Memory & AST Blast-Radius Impact Analyzer
  ├── Level 7: Dynamic Tool Discovery, Sandboxing & Bayesian EWMA Reliability Rating
  ├── Level 8: Capability-Based Model Routing & Cognitive USD Budget Tracker
  ├── Level 9: Execution Sandbox with Filesystem Snapshot & Zero-Loss Rollback
  └── Level 10: Drift Detection & Autonomous Self-Improvement Benchmark Suite
========================================================================================
```

---

## 🆓 Built-in 100% FREE Models (Zero API Keys Required!)

Titan Agent has **native built-in support for free, keyless, and local models out-of-the-box**. You can run the entire system completely free without entering a single credit card or paid API key:

| Provider | Access Mode | Cost | Supported Models | How to Run |
|---|---|:---:|---|---|
| **Puter.js** | Cloud (Keyless) | **FREE** | **500+ Models**: DeepSeek V4 Pro / R1, Claude 3.5 Sonnet, GPT-4o, Llama 3.3 70B, Qwen 2.5 | `python cli.py --provider puter --model deepseek/deepseek-v4-pro` |
| **Completions.me** | Cloud Gateway | **FREE** | Claude Opus, GPT-5 class, Gemini Pro, Grok | `python cli.py --provider completions --model claude-sonnet-4.5` |
| **Laya MLX** | Local (PC / Mac) | **FREE** | Local MLX-quantized models with hardware acceleration | `python cli.py --provider laya-mlx --model local` |
| **Ollama** | Local (Offline) | **FREE** | DeepSeek-R1, Llama 3.2, Mistral, Qwen, CodeLlama | `python cli.py --provider ollama --model deepseek-r1:8b` |
| **LM Studio** | Local (Offline) | **FREE** | Any GGUF model running on `localhost:1234` | `python cli.py --provider lmstudio --model local-model` |
| **GPT4Free (`g4f`)** | Multi-Provider | **FREE** | Keyless OpenAI/Anthropic proxy scrapers | `python cli.py --provider g4f` |
| **Python-tGPT (`tgpt`)** | Multi-Provider | **FREE** | Terminal-native keyless AI models | `python cli.py --provider tgpt` |
| **OmniRoute** | Self-Hosted | **FREE** | Auto-routing smart gateway (`auto`, `auto/coding`, `auto/fast`, `auto/cheap`) | `python cli.py --provider omni --model auto` |

> 💡 **Tip**: In `.env`, simply leave API keys blank and set `TITAN_PROVIDER=puter` or `TITAN_PROVIDER=ollama` to run Titan Agent 100% free forever!

---

## 🌟 Key Technical Innovations & Specifications

### 1. 🏛️ Hierarchical Delegation & Role Specialization (Level 1 & 2)
- **CEO Meta-Orchestrator** (`orchestrator.py`): Persists multi-turn session state, allocates computing budgets, and arbitrates competing agent directives.
- **4 Department Team Leads** (`team_leads.py`): Each departmental lead performs pre-flight goal decomposition, dispatches worker sub-tasks, and validates output quality before reporting up the hierarchy.
- **27 Specialist Workers** (`staff.py`): Dedicated operational personas with granular tool permissions, eliminating context contamination.

### 2. 📊 Directed Acyclic Graph (DAG) Task Planner & Wave Executor (Level 4)
- **Topological Wave Execution** (`core/dag/`): Deconstructs composite goals into dependency graphs using Kahn's algorithm. Independent nodes run concurrently in parallel execution waves (`max_concurrency=4`).
- **Selective Replanning**: When a node fails, the planner isolates the failed branch and only replans affected downstream nodes, preserving the work of successful independent tasks.

### 3. 🧠 Dual Cognitive Reasoning Engines (Level 5)
- **Reflexion Loop** (`core/reasoning/reflexion.py`): A continuous self-critique loop. The agent evaluates its candidate solutions against strict success criteria, iteratively revising code and hypotheses up to 3 cycles.
- **Multi-Agent Debate Arena** (`core/reasoning/debate.py`): Pitches an **Advocate** (proposing architecture and solutions) against a **Skeptic** (uncovering edge-cases, race conditions, and attack vectors). An **Arbitrator Judge** synthesizes the winning consensus.

### 4. 🌐 Causal Knowledge Graph & AST Code Intel (Level 6)
- **Workspace AST Extractor** (`core/memory/ast_graph_extractor.py`): Statically parses the entire Python workspace, constructing an automated graph of classes, functions, imports, and call dependencies.
- **Blast Radius & Impact Analysis**: Before modifying any function or file, Titan computes affected downstream callers and modules (`kg_impact_analysis`), preventing unintended regression bugs.

### 5. 🛠️ Dynamic Tool Discovery & Reliability Telemetry (Level 7)
- **Context-Aware Dynamic Registry** (`core/tools/dynamic_registry.py`): Solves the 60+ tool prompt-bloat problem. Groups tools into domain bundles (`git`, `web`, `genesis_orchestrator`, `reasoning`, `knowledge_graph`, `desktop_os`, `sandbox_verify`) and dynamically injects only relevant schemas, reducing tool tokens by ~75%.
- **Bayesian EWMA Reliability Tracker** (`core/tools/reliability.py`): Grades every tool from **Grade A to F** based on real-time execution success rates and generates automated mitigation advice for brittle tools.

### 6. 🎯 Capability-Based Model Routing & Cognitive Budget (Level 8)
- **Smart Model Tiering** (`core/routing/model_router.py`):
  - `FAST_CHEAP`: Lightweight summaries, lookups, formatting (`gpt-4o-mini`, `gemini-1.5-flash`, `claude-3-5-haiku`).
  - `STANDARD_CODING`: Complex engineering, API implementation, refactoring (`claude-3-5-sonnet`, `gpt-4o`, `deepseek-coder`).
  - `DEEP_REASONING`: Formal logic, architectural trade-offs, debate synthesis (`o3-mini`, `deepseek-reasoner`, `o1`).
- **Dynamic Failure Escalation**: Automatically elevates task execution to higher reasoning tiers upon detecting retries or syntax failures.
- **Cognitive Budget Tracker** (`core/routing/cost_tracker.py`): Real-time per-turn token and USD spend tracking with hard safety budget limits.

### 7. 🛡️ Execution Sandbox & Zero-Loss Rollback (Level 9)
- **Filesystem Snapshot Engine** (`core/sandbox/environment.py`): Captures byte-level workspace snapshots with SHA-256 integrity hashes prior to destructive actions.
- **Transactional Rollback**: Reverts modified files to their original byte state, restores deleted files, and permanently deletes rogue files generated by failed runs.
- **Static Security Guard** (`core/sandbox/safe_runner.py`): Blocks fork-bombs (`:(){ :|:& };:`), root wipes (`rm -rf /`), and drive format operations before execution.

### 8. 📉 Longitudinal Drift Detection & Performance Monitoring (Level 10)
- **Statistical Quality Tracking** (`core/monitoring/drift_detector.py`): Compares recent execution metrics against historical baselines.
- **Automated Regression Alerts**: Flags **Success Rate Drops** (>= 20% `WARNING`, >= 35% `CRITICAL`), **Step Inflation** (>= 1.8x baseline steps), and isolates recurrent tool failure clusters.

### 9. 👑 Autonomous Self-Improvement Loop & Eval Benchmark Suite (Level 10)
- **Failure Root-Cause Learning** (`core/self_improvement/learning_engine.py`): Extracts actionable lessons from failed tasks and formulates prescriptive operational rules.
- **Permanent Knowledge Crystallization**: Persists distilled insights into `SkillRegistry` playbooks and links causal avoidance facts into the `KnowledgeGraph`.
- **Regression Eval Suite** (`core/self_improvement/eval_suite.py`): Automated test suite benchmark validating coding, reasoning, security, and Git operations.

---

## 📋 System Requirements & Prerequisites

### Required:
- **Operating System**: Windows 10/11, macOS (Apple Silicon M-Series or Intel), or Linux (Ubuntu 20.04+, Debian, Fedora).
- **Python**: **Python 3.11** or **Python 3.12+**.
- **Git**: Installed and available in system `PATH`.
- **Memory (RAM)**: Minimum 4 GB RAM (8 GB – 16 GB recommended).

### Supported LLM Providers:
- **Commercial APIs**: OpenAI (`gpt-4o`, `o3-mini`), Anthropic Claude (`claude-3-5-sonnet`), Google Gemini, DeepSeek (`deepseek-reasoner`, `deepseek-coder`).
- **Local & Offline Runners (100% Free & Private)**:
  - **Laya MLX** (Apple Silicon / PC local model server).
  - **Ollama** (`http://localhost:11434` — Llama 3, DeepSeek-R1, Qwen, Mistral).
- **Zero-Key In-Browser Provider**:
  - **Puter.js / OmniRoute**: Instant access to 500+ frontier models directly without requiring API keys.

---

## 🚀 Installation & Setup Guide

### Step 1: Clone the Repository
```bash
git clone https://github.com/kapitan00000978-sketch/Titan-agent-.git
cd Titan-agent-
```

### Step 2: Create and Activate Virtual Environment
**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
Copy `.env.example` to create your local `.env`:
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and specify your preferred keys or local endpoints:
```ini
# Primary LLM Provider (omni, openai, anthropic, deepseek, ollama, puter)
TITAN_PROVIDER=omni
TITAN_MODEL=auto

# Optional API Keys (Leave blank if using local Ollama or Puter.js)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=
GEMINI_API_KEY=

# Local Model Endpoints
OLLAMA_BASE_URL=http://localhost:11434
LAYA_MLX_URL=http://127.0.0.1:8080

# Safety & Cognitive Budget
COGNITIVE_BUDGET=5.00
TITAN_AUTONOMOUS=true
```

---

## 🎮 Execution Modes

Titan Agent can be operated through three interfaces:

### 1. 🌐 Web Control Panel (Modern Cyberpunk Dashboard)
Launches the FastAPI server and opens the browser interface:
```bash
python run.py
```
*Access via: `http://localhost:8000` (Features live streaming, DAG visualizer, model routing inspect, and tool reliability logs).*

### 2. 💻 Interactive Terminal CLI
Full-featured terminal console with syntax highlighting, streaming output, and REPL slash commands:
```bash
python run.py --cli
# Or directly:
python cli.py
```

#### Autonomous One-Shot CLI Commands:
```bash
# Run task using CEO Meta-Orchestrator & Team Leads:
python cli.py --meta "Build an authenticated JWT REST API in FastAPI with SQLite"

# Run task using DAG Wave-Based Parallel Planner:
python cli.py --dag "Refactor backend database schema and implement complete pytest suite"

# Execute task with Multi-Agent Debate Strategy:
python cli.py --strategy debate "Should we migrate the monolith to microservices or modular monolith?"

# Run task using Reflexion Self-Critique Engine:
python cli.py --strategy reflexion "Write an optimal concurrent LRU Cache in Python with thread locks"

# Delegate directly to a specialized staff member:
python cli.py --staff SecurityAuditor "Scan codebase for injection vectors and hardcoded secrets"
```

### 3. 🤖 Remote Telegram Bot
Control and interact with Titan Agent securely from your phone:
```bash
python run.py --telegram
```

---

## 🛠️ Built-in Tool Ecosystem

| Category | Key Tools | Description |
|---|---|---|
| **Genesis Meta** | `orchestrator_run`, `team_delegate`, `team_status` | CEO Meta-Orchestrator delegation across 4 department leads. |
| **Task Graph (DAG)** | `dag_plan_and_run`, `dag_visualize` | Topological wave execution and selective failure replanning. |
| **Cognitive Reasoning** | `debate_solve`, `reflexion_solve` | Adversarial debates and iterative self-critique loops. |
| **Knowledge Graph** | `kg_query`, `kg_impact_analysis`, `kg_index_workspace` | AST codebase scanning, dependency tracing, blast-radius analysis. |
| **Dynamic Tools** | `tool_discover`, `tool_reliability_report` | Dynamic tool discovery and Bayesian EWMA health ratings. |
| **Model Routing** | `model_route`, `model_budget_status` | Complexity-based tier routing and USD expenditure auditing. |
| **Execution Sandbox** | `sandbox_execute`, `sandbox_snapshot_create`, `sandbox_snapshot_rollback` | Ephemeral code execution with transactional filesystem rollback. |
| **Drift Monitoring** | `drift_record_task`, `drift_check`, `drift_status` | Longitudinal performance tracking and quality degradation detection. |
| **Self-Improvement** | `self_improve_analyze_failure`, `self_improve_eval_run`, `self_improve_crystallize_lesson` | Autonomous failure learning, prompt evolution, and skill crystallization. |
| **Core Workspace** | `read_file`, `write_file`, `edit_file`, `execute_command`, `workspace_rag` | Robust filesystem manipulation, AST patching, and terminal execution. |
| **Web & Research** | `web_search`, `scrape_webpage`, `download_file` | Live DuckDuckGo search, HTML extraction, and research dossier builder. |
| **OS & Automation** | `browser_goto`, `browser_click`, `browser_screenshot`, `manage_processes` | Full Playwright web automation and Windows/macOS process management. |

---

## 🧪 Comprehensive Verification & Test Suite

Titan Agent maintains a 100% green test pass rate across all 30 phases:

```bash
python -m pytest tests -v
```

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\user\Videos\demo1
configfile: pytest.ini

...
================== 600 passed, 1 skipped in 74.25s (0:01:14) ==================
All checks passed! (Ruff linting clean)
```

---

## 📖 Operational Rules & Manual
For the exhaustive 380-line English operational rulebook, laws of engagement, and troubleshooting instructions, refer to **[TITAN_AGENT_MANUAL.txt](TITAN_AGENT_MANUAL.txt)**.

---

## 📄 License
This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.