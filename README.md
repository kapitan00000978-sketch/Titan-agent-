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

## Key Capabilities

- **Mission Control Dashboard & Telemetry:** Real-time state-machine visualizer (`Intent -> Guardrail -> MCTS Plan -> Tool Exec -> Deep Verifier -> Delivery`), live tool performance matrix, and system logs.
- **AST Code Intelligence:** Tree-aware surgical code replacement for functions and classes via `ASTPatcher` to prevent indentation and syntax regressions.
- **Deep Test-Driven Verification:** Self-healing verification loop that autonomously generates `pytest` suites and verifies code in isolated environments before returning results.
- **Dual-Shield Cyber Defense:** In-line Blue Team monitoring, prompt injection defense, and automated secret exfiltration guards.
- **Flexible Provider Brains:** Supports local zero-cost models (`Ollama`) as well as high-throughput cloud endpoints (`Groq`, `Google Gemini`, `OpenRouter`, `DeepSeek`, `Claude`, `OpenAI`).

## Architecture Overview

The system uses a straightforward orchestrator-worker model to manage tasks:

`mermaid
graph TD
    A[User Request] --> B(Universal CLI)
    B --> C{Orchestrator}
    C --> D[Task Planner]
    C --> E[Security Auditor]
    D --> F[Worker Agent]
    F --> G[(Memory/State)]
    F --> H[Execution Sandbox]
    H --> F
    F --> C
    C --> I[Output to User]
`

## Testing & Security
- **Tests:** Run the test suite with pytest tests/.
- **Security:** Static analysis and secret scanning tools are integrated into the pipeline. (See CI reports for details).

## Contributing
We welcome contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Releases
For a history of stable releases and versioning, check the [Releases page](https://github.com/example/titan_agent/releases).

## License
MIT License
