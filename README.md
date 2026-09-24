# Titan Agent (Universal Agent HP)

[![Build Status](https://github.com/kapitan00000978-sketch/Universal-Agent-HP/actions/workflows/tests.yml/badge.svg)](https://github.com/kapitan00000978-sketch/Universal-Agent-HP/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Titan Agent is an autonomous AI agent framework designed for executing coding tasks, running tests, and managing workflows in an isolated environment.

![MVP Demo](https://via.placeholder.com/800x400.png?text=Working+MVP+Demo+GIF)

## ⚠️ Important Notice Regarding Free Model Access
This project includes experimental integrations that allow "free" access to models via unofficial proxies (e.g., Puter.js, g4f, tgpt). 
**Disclaimer:** These methods rely on unverified third-party reverse-proxies. They are unofficial, guarantee no uptime or privacy, and may violate the original provider's Terms of Service. They can break or be blocked at any time. We strongly recommend setting `TITAN_PROVIDER` to official APIs (like `groq`, `gemini`, `openrouter`) or using local models (`ollama`) for stability and security.

## Installation

### Prerequisites
- Python 3.10+
- Git

### Setup
`ash
# Clone the repository
git clone https://github.com/kapitan00000978-sketch/Universal-Agent-HP.git
cd Universal-Agent-HP

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .
`

### Configuration
Copy the environment template and set your API keys:
`ash
cp .env.example .env
`

## Quick Start
Run a simple one-shot task:
`ash
universal "Write a python script that prints Hello World"
`

Start the interactive terminal CLI:
`ash
universal
`

Launch the web dashboard:
`ash
universal --web
`

## Key Capabilities (Next-Gen Universal Agent)

- **Tri-Loop Metacognitive Reasoning Engine:**
  - **System 1 (Fast Intuition):** 0ms pattern-matched instant path bypassing heavy tool reasoning for simple queries.
  - **System 2 (Deliberative Planning):** Multi-hop ReAct, Tree-of-Thoughts, and Monte Carlo Tree Search (MCTS) with Bayesian candidate hypothesis tracking.
  - **System 3 (Metacognitive Overseer):** Real-time monitoring of Shannon cognitive entropy, hallucination drift, and cyclic dead-ends with autonomous strategy pivoting (MCTS, Adversarial Debate, or Tool Synthesis).
- **On-The-Fly Autonomous Tool & Skill Synthesis:** When a task requires capabilities not present in static registries, the agent writes the Python tool, executes verification tests in an isolated sandbox, compiles it, and hot-injects it into `ToolRegistry` during the live session.
- **Symbolic AST Invariant Checker:** Statically scans Python code prior to execution to detect infinite loops (`while True` without escape), command injection hazards, and resource leaks.
- **Mission Control Dashboard & Telemetry:** Real-time state-machine visualizer (`[01. Intent Routing] -> [02. Dual-Shield Guard] -> [03. Planning & MCTS] -> [04. Tool Execution] -> [05. Deep Verification] -> [06. Verified Delivery]`), live tool performance matrix, and real-time SSE event log streaming.
- **AST Code Intelligence & Surgical Patching:** Boundary-accurate replacement for functions and classes via `ASTPatcher`, preventing line-number offset errors.
- **Deep Test-Driven Verification:** Self-healing verification loop that autonomously runs `pytest` in isolated sandboxes with Docker or native fallback.
- **Dual-Shield Cyber Defense:** Integrated Blue Team security sentinels and emergency Red Team forensic analysis.

## Architecture: Tri-Loop Metacognitive Execution

```mermaid
graph TD
    User([User Request]) --> Router[Multilingual Intent Router]
    Router --> Shield{Dual-Shield Guard}
    Shield -- Allowed --> TriLoop[Tri-Loop Reasoning Core]
    
    subgraph "Tri-Loop Metacognitive Architecture"
        TriLoop --> S1[System 1: Fast Heuristics 0ms]
        TriLoop --> S2[System 2: Deliberative ReAct / MCTS]
        TriLoop --> S3[System 3: Metacognitive Overseer]
        
        S2 <--> Bayes[(Bayesian Hypotheses)]
        S2 <--> ToolExec[Concurrent Tool Execution]
        
        S3 -. Entropy & Drift Monitored .-> S2
        S3 -. Stuck Detected: Trigger Synthesis .-> Synth[Dynamic Tool Synthesizer]
        Synth -. Sandbox Tested & Injected .-> ToolExec
    end
    
    ToolExec --> PostCheck{Symbolic & AST Postcheck}
    PostCheck -- Verified --> Output([Verified Delivery])
```

## 120-Stage Master Architecture Blueprint

The project is governed by a 120-stage progressive evolution roadmap spanning 6 core capability tracks:
1. **Stages 001–020:** Metacognitive Core & Tri-Loop Engine (Entropy, Bayesian Belief, Stagnation Breakers).
2. **Stages 021–040:** Autonomous Dynamic Tool & Skill Synthesis (Hot-Reloading, Sandbox Verifier, API Reverse-Engineering).
3. **Stages 041–060:** Deep Code Intelligence & Symbolic Invariants (AST Invariant Prover, Mutation Testing, Dependency Conflict Resolver).
4. **Stages 061–080:** Hierarchical Multi-Agent Swarm & Raft Consensus (Meta-Orchestrator, Department Leads, Raft Voting).
5. **Stages 081–100:** Persistent Multi-Tier Memory & Knowledge Graph (Causal Impact Analysis, WAL High Concurrency Storage).
6. **Stages 101–120:** Multimodal Telemetry, Visual Self-Correction & Industrial Delivery (Playwright DOM Inspector, Singularity Auto-Evolution).

## Testing & Security
- **Tests:** Run the test suite with `pytest tests/` (103+ unit & integration tests).
- **Security:** Static analysis, AST invariant checking, and secret scanning are integrated directly into the tool execution funnel.

## Contributing
We welcome contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Releases
For a history of stable releases and versioning, check the [Releases page](https://github.com/example/titan_agent/releases).

## License
MIT License
