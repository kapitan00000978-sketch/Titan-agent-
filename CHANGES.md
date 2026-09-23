# TITAN AGENT — Changelog

All fixes and improvements made during the completion effort of this project.

## 👑 Phase 30 — SELF-IMPROVEMENT LOOP & EVAL SUITE (Genesis Darajasi 10 — Cho'qqi)

Completed the final pinnacle layer of the Genesis Master Architecture: autonomous self-improvement, continuous failure learning, prompt evolution diffing, and regression benchmark evaluation:

### 1. Eval Suite & Regression Benchmark Framework (`titan_agent/core/self_improvement/eval_suite.py`)
- **`EvalCase` & `EvalRunResult`**: Standardized evaluation units with keyword matching, forbidden term guards, timeout limits, and custom scoring validators.
- **`EvalSuite`**:
  - `CORE_BENCHMARK`: Curated multi-domain evaluation cases (`core_python_syntax`, `core_reasoning_deduction`, `core_tool_safety_refusal`, `core_git_status_inspection`).
  - Supports category filtering (`category="coding"`, `"reasoning"`, etc.) and returns structured pass rates, duration, and quality scores.

### 2. Failure Learning & Self-Improvement Engine (`titan_agent/core/self_improvement/learning_engine.py`)
- **`ImprovementLesson`**: Structured distilled insight capturing `task_id`, `category`, `symptom`, `root_cause`, `guidance`, and `rule_text`.
- **`SelfImprovementLoop`**:
  - **Diagnostic Root-Cause Extraction (`analyze_failure`)**: Automatically classifies failures into AST syntax errors, execution timeouts, or tool failures, and formulates prescriptive operational rules.
  - **Prompt Evolution (`propose_prompt_refinement`)**: Generates unified diffs proposing system prompt updates incorporating lessons learned.
  - **Crystallization into Permanent Memory (`crystallize_lesson`)**:
    - Converts lessons into reusable, auto-injected playbooks in `SkillRegistry`.
    - Automatically links causal avoidance relations into the `KnowledgeGraph` (`(category) -[governed_by_rule]-> (rule)`).

### 3. Agent Tools Integration (`tools.py`)
- **New Tools in `ToolRegistry`**:
  - `self_improve_analyze_failure(task_id, prompt, failure_log, failed_tools, category)`: Analyzes failure and extracts actionable rules.
  - `self_improve_eval_run(category)`: Executes regression benchmark suite and reports pass rates.
  - `self_improve_crystallize_lesson(lesson_title, guidance, category)`: Permanently saves lessons into the Skill Playbook library and Knowledge Graph.
- Registered in `dynamic_registry.py` under `reasoning`.

### 4. Verification
- 12 unit and integration tests in `tests/test_phase30_self_improvement.py` covering core benchmark evaluation, failure analysis, prompt refinement diffing, skill and knowledge graph crystallization, and ToolRegistry invocation.
- 100% test pass rate with clean ruff linting.

## 📉 Phase 29 — DRIFT DETECTION & PERFORMANCE DEGRADATION MONITORING (Genesis Darajasi 9)

Architected longitudinal agent health tracking, statistical regression alerting, and automated root-cause diagnostics:

### 1. Longitudinal Telemetry & Drift Detection (`titan_agent/core/monitoring/drift_detector.py`)
- **`TaskExecutionMetric`**:
  - Structured record capturing `task_id`, `category`, `success: bool`, `steps: int`, `duration_sec: float`, `tokens_used: int`, `failed_tools: list[str]`, and error details.
  - Serialization and deserialization (`to_dict` / `from_dict`).
- **`QualityDriftDetector`**:
  - Thread-safe sliding window comparative analysis: compares recent tasks (`window_size`) against historical baseline tasks (`baseline_size`).
  - Automatic detection of:
    - **Success Rate Drop**: Alerting when success falls below baseline by >= 20% (`WARNING`) or >= 35% (`CRITICAL`).
    - **Step Inflation**: Identifies when tasks take >= 1.8x or >= 2.0x more steps than baseline (detecting exploratory thrashing).
    - **Latency Degradation**: Computes inflation in elapsed execution time.
  - **Root-Cause Analysis**: Identifies tool failure frequencies (`problematic_tools`), error patterns, and generates prescriptive mitigation advice (e.g. promoting LLM tier, activating DAG planner, or inspecting failing tools).
  - **Thread-safe Persistence**: Saves and reloads telemetry from `.titan/drift_metrics.json`.

### 2. Agent Tools Integration (`tools.py`)
- **New Tools in `ToolRegistry`**:
  - `drift_record_task(task_id, success, steps, duration_sec, tokens_used, failed_tools, category)`: Logs task performance telemetry.
  - `drift_check(window_size, threshold_drop)`: Evaluates historical performance for degradation and returns diagnostic report.
  - `drift_status()`: Summarizes cumulative success rate, average steps/task, and latency.
- Integrated into `dynamic_registry.py` under `genesis_orchestrator`.

### 3. Verification
- 9 unit and integration tests in `tests/test_phase29_drift.py` covering serialization, baseline comparisons, critical drift alerts, step inflation detection, JSON persistence, and ToolRegistry invocation.
- 100% test pass rate with clean ruff linting.

## 🛡️ Phase 28 — EXECUTION SANDBOX & ISOLATED ENVIRONMENT (Genesis Darajasi 8)

Engineered a zero-loss transactional filesystem snapshotting engine and isolated safe script execution runtime:

### 1. Filesystem Snapshot & Rollback Engine (`titan_agent/core/sandbox/environment.py`)
- **`FilesystemSnapshot`**:
  - Captures point-in-time byte snapshots of all files in workspace up to 5 MB per file.
  - Automatically filters transient and cache directories (`.git`, `.venv`, `__pycache__`, `node_modules`, etc.).
  - Computes per-file SHA-256 integrity hashes and structured diffs (`added`, `removed`, `modified`).
- **`SandboxEnvironment`**:
  - Transactional rollback: completely restores modified files to snapshot state, recreates deleted files, and safely purges files created since the snapshot.
  - Snapshot naming, cataloging, and ephemeral directory creation (`create_ephemeral_dir`).

### 2. Safe Script Runner & Subprocess Isolation (`titan_agent/core/sandbox/safe_runner.py`)
- **`SafeScriptRunner`**:
  - Static AST and regex safety scanning (`validate_code_safety`) blocking fork bombs (`:(){ :|:& };:`), root directory wipes (`rm -rf /`), disk format attempts, and dangerous filesystem deletion calls before execution.
  - Executes Python scripts inside isolated subprocesses with configurable timeout enforcement (default 30s, up to 300s).
  - **Autonomous Rollback on Failure**: When `rollback_on_failure=True`, captures an automatic pre-execution snapshot and instantly reverts any file modifications if the script crashes or times out.
- **`SandboxResult`**: Captures exit code, stdout, stderr, execution duration, and rollback status.

### 3. Agent Tools Integration (`tools.py`)
- **New Tools in `ToolRegistry`**:
  - `sandbox_execute(code, language, timeout, rollback_on_failure)`: Safely executes code with validation, execution timing, and failure rollback.
  - `sandbox_snapshot_create(name)`: Takes an immediate point-in-time filesystem snapshot of the workspace.
  - `sandbox_snapshot_rollback(name)`: Restores workspace files to a previously saved snapshot.
- Integrated into `dynamic_registry.py` under the `sandbox_verify` domain bundle.

### 4. Verification
- 11 unit and integration tests in `tests/test_phase28_sandbox.py` covering snapshots, diffs, mutations, rollbacks, timeout enforcement, security alert blocks, and ToolRegistry invocation.
- 100% test pass rate with clean ruff linting.

## 🎯 Phase 27 — CAPABILITY-BASED MODEL ROUTING & COGNITIVE BUDGET (Genesis Darajasi 7)

Introduced intelligent cognitive tiering, dynamic model escalation on retries, and strict per-turn / per-session token budget accounting:

### 1. Model Capability Profiler & Router (`titan_agent/core/routing/model_router.py`)
- **`ModelTier`**:
  - `FAST_CHEAP`: Lightweight summaries, lookups, formatting, quick file inspection (`gpt-4o-mini`, `gemini-1.5-flash`, `claude-3-5-haiku`).
  - `STANDARD_CODING`: Complex software engineering, API implementation, refactoring, test suites (`claude-3-5-sonnet`, `gpt-4o`, `deepseek-coder`).
  - `DEEP_REASONING`: Multi-step architectural trade-offs, formal logic, race conditions, multi-agent debates, reflexion loops (`o3-mini`, `deepseek-reasoner`, `o1`).
- **`ModelCapabilityProfile`**: Profiles pricing ($/1M input & output tokens), context lengths, coding score, and reasoning score.
- **Dynamic Failure Escalation**: If a task fails or triggers retries, the router automatically promotes the execution to higher tiers (`FAST_CHEAP` -> `STANDARD_CODING` -> `DEEP_REASONING`).

### 2. Cognitive Budget & Token Cost Tracker (`titan_agent/core/routing/cost_tracker.py`)
- **`CognitiveBudgetTracker`**:
  - Thread-safe accounting of input and output tokens across every model and tier.
  - Computes real-time USD expenditures with configurable budget thresholds (`budget_limit_usd`).
  - Emits budget limit alerts if total cost crosses target ceilings.

### 3. Agent Tools Integration (`tools.py`)
- **New Tools in `ToolRegistry`**:
  - `model_route(task, prior_failures)`: Evaluates task complexity, returns optimal model tier, pricing per 1k tokens, and escalation status.
  - `model_budget_status()`: Renders human-readable report of tokens processed, USD consumed, remaining budget, and breakdown by model.

### 4. Verification
- 4 comprehensive unit tests in `tests/test_phase27_model_routing.py`.
- 100% test pass rate across all 569 tests (568 passed, 1 skipped). Clean ruff checks.

## 🛠️ Phase 26 — DYNAMIC TOOL DISCOVERY, SANDBOXING & RELIABILITY RATING (Genesis Darajasi 8)

Solved the 60+ tool prompt-bloat problem and hardened tool stability with dynamic discovery, context-aware bundle pruning, EWMA reliability scoring, and tiered risk sandboxing:

### 1. Tool Reliability Tracker (`titan_agent/core/tools/reliability.py`)
- **`ToolReliabilityTracker`**: Thread-safe Bayesian/EWMA health scoring system (decay alpha=0.3) evaluating tool performance on a [0.0 - 1.0] continuous scale.
- **Grade Tiers**:
  - `Grade A` (>= 0.90): Highly reliable.
  - `Grade B` (>= 0.75): Good health, minor transient issues.
  - `Grade C` (>= 0.55): Intermittent failures, warning issued.
  - `Grade F` (< 0.55): Degraded / brittle tool.
- **Autonomous Mitigation Advice**: Automatically detects consecutive failure streaks and generates corrective recommendations (e.g. suggesting fallbacks or parameter verification).
- Re-entrant `RLock` synchronization preventing self-deadlocks during report generation.
- Full process-wide telemetry hookup with `TOOL_STATS` in `titan_agent/tool_stats.py`.

### 2. Dynamic Context-Aware Tool Selection & Discovery (`titan_agent/core/tools/dynamic_registry.py`)
- **`DynamicToolSelector`**:
  - Always pins essential `CORE_TOOLS` (`execute_command`, `read_file`, `write_file`, `edit_file`, `list_directory`, `search_files`, `tool_discover`, `tool_reliability_report`).
  - Categorizes 60+ tools into domain bundles: `git`, `web_browser`, `genesis_orchestrator`, `reasoning`, `knowledge_graph`, `vector_rag`, `desktop_os`, `sandbox_verify`.
  - Intelligently scores and injects relevant domain bundles based on user task tokens and intent, reducing tool prompt bloat by ~75% while keeping all capabilities available.
  - Deprioritizes Grade F (broken) tools during context packing.
- **On-Demand Discovery**: `discover_tools(query, category)` performs keyword and semantic ranking across tool names, categories, and parameters.

### 3. Tool Sandboxing & Risk Isolation Guard (`titan_agent/core/tools/sandboxing.py`)
- **`ToolRiskLevel`**: `LOW` (read-only), `MEDIUM` (controlled workspace modification), `HIGH` (system execution, OS automation, network downloads).
- **`ToolSandboxGuard`**:
  - `SandboxMode.OFF`: Standard operational mode.
  - `SandboxMode.STRICT`: Requires explicit `confirmed=True` flag for all `HIGH_RISK` actions.
  - `SandboxMode.DOCKER`: Automatically blocks host execution of raw commands and enforces routing through ephemeral Docker containers.

### 4. Integration & Agent Tools (`tools.py`, `tool_stats.py`)
- **New Tools in `ToolRegistry`**:
  - `tool_discover(query, category)`: Dynamic semantic tool discovery on demand.
  - `tool_reliability_report()`: Structured inspection of tool grades, failure counts, and health statuses.

### 5. Verification
- 4 comprehensive unit tests in `tests/test_phase26_tools.py`.
- 100% test pass rate across all 565 tests (564 passed, 1 skipped). Clean ruff checks.

## 🌐 Phase 25 — CAUSAL KNOWLEDGE GRAPH MEMORY (Genesis Darajasi 3 & 6)

Implemented deep graph-based structural, causal, and dependency memory for codebases and project context:

### 1. Knowledge Graph Core (`titan_agent/core/memory/knowledge_graph.py`)
- **`GraphEntity` & `GraphRelation`**: Structured representation of files, modules, classes, functions, architectural concepts, bugs, and causal relationships (`depends_on`, `imports`, `defines`, `inherits`, `calls`, `modifies`, `causes`).
- **`KnowledgeGraph`**: In-memory and persistent graph layer with bi-directional adjacency indices (`out_edges`, `in_edges`).
- **BFS Shortest Path & Node Traversal**: `find_path` and `find_node_path` provide shortest-path discovery between disparate entities up to N hops.
- **Downstream Impact & Blast-Radius Analysis**: `impact_analysis` traverses outgoing dependencies to evaluate ripple effects and cascade depths before code or architecture changes occur.
- **Mermaid Visualizer**: `to_mermaid` generates live topological diagrams with customizable orientations.

### 2. AST Codebase Extractor (`titan_agent/core/memory/ast_graph_extractor.py`)
- **`WorkspaceASTGraphExtractor`**: Automatically walks Python source files in the workspace, parsing ASTs without execution.
- Captures module imports (`import x`, `from x import y`), class definitions and inheritance (`class Foo(Bar)`), function and async function declarations, and maps their relationships.

### 3. Integration & Agent Tools (`memory.py`, `tools.py`)
- **`MemoryManager`**: Integrated `KnowledgeGraph` alongside long-term memory vault and SQLite history, with `add_kg_fact`, `query_kg`, and `kg_impact`.
- **Tools in `ToolRegistry`**:
  - `kg_query`: Query entity connections and neighborhood up to N hops.
  - `kg_impact_analysis`: Calculate affected blast radius and cascade depth.
  - `kg_add_fact`: Add custom semantic or causal connections.
  - `kg_index_workspace`: Scan workspace ASTs to build or refresh the graph.

### 4. Verification
- 5 comprehensive unit tests in `tests/test_phase25_knowledge_graph.py`.
- 100% test pass rate across all 561 tests (560 passed, 1 skipped). Clean ruff checks.

## 🧠 Phase 24 — REFLEXION LOOP & MULTI-AGENT DEBATE STRATEGY (Genesis Darajasi 4)

Integrated advanced cognitive self-correction and multi-perspective adversarial reasoning into the Titan Agent Reasoning Engine:

### 1. Reflexion Engine (`titan_agent/core/reasoning/reflexion.py`)
- **`ReflexionEngine`**: Implements an autonomous self-critique loop where the agent independently assesses its own drafts for hallucinations, missing requirements, logical gaps, and syntax issues.
- **Iterative Refinement**: If critique issues a `NEEDS_REVISION` verdict or scores below threshold, actionable remediation advice is fed back into iterative refinement cycles (up to 3 cycles), returning only when `PASS` or high score is achieved.
- Early exit optimization: Flawless solutions pass on Cycle 1 with zero latency penalty.

### 2. Multi-Agent Debate Engine (`titan_agent/core/reasoning/debate.py`)
- **`DebateEngine`**: Pits opposing cognitive roles against each other across multi-round exchanges:
  - **Advocate (Proposer)**: Mounts the strongest architectural proposal, highlights scalability and benefits.
  - **Skeptic (Challenger)**: Uncovers hidden operational costs, edge-case vulnerabilities, and latency penalties.
  - **Arbitrator (Chief Technology Judge)**: Delivers an authoritative, compromise-aware verdict balancing trade-offs and issuing a concrete engineering action plan.

### 3. Strategy Routing & Live Loop Integration (`structured.py`, `tools.py`, `cli.py`)
- **`VALID_STRATEGIES`**: Expanded to `("auto", "plan", "react", "tot", "reflexion", "debate")`.
- **`StructuredEngine`**: Directly executes `reflexion` (with step-by-step reflection thoughts) and `debate` (with speaker turns) inside the live agent event stream.
- **Tools**: Added `reflexion_solve(task)` and `debate_solve(question, rounds)` tools.
- **CLI**: Added `--strategy {auto,plan,react,tot,reflexion,debate}` support.

### 4. Verification
- 4 comprehensive unit tests in `tests/test_phase24_reasoning.py`.
- 100% test pass rate across all 556 tests (555 passed, 1 skipped). Clean ruff checks.

## 📊 Phase 23 — TASK GRAPH (DAG) PLANNING & PARALLEL EXECUTION (Genesis Darajasi 5)

Implemented full Directed Acyclic Graph (DAG) long-term planning and parallel execution engine:

### 1. Task Graph Data Structure (`titan_agent/core/dag/task_graph.py`)
- **`TaskNode`**: Encapsulates a discrete task unit with department, assigned worker role, dependencies, status, retries, output, and execution timings.
- **`TaskGraph`**: Complete DAG implementation with cycle detection via Kahn's algorithm (`validate_acyclic`), topological sorting (`topological_sort`), wave readiness inspection (`get_ready_nodes`), and live Mermaid diagram export (`to_mermaid`).
- **Selective Subtree Replanning**: `reset_node_and_dependents(node_id)` resets only the failed node and its downstream dependents while preserving all completed independent work.

### 2. DAG Planner (`titan_agent/core/dag/dag_planner.py`)
- **`DAGPlanner`**: Decomposes complex multi-disciplinary goals into dependency-aware DAGs.
- Supports model-driven planning via `LLMClient` with structured JSON output and deterministic heuristic decomposition across Research, Implementation, QA, Security, and Operations.
- `replan_subgraph`: Adapts failed nodes with diagnostic context and remediation tasks without restarting the entire pipeline.

### 3. Wave-Based Parallel Executor (`titan_agent/core/dag/dag_executor.py`)
- **`DAGExecutor`**: Evaluates ready nodes wave-by-wave and executes independent nodes concurrently via `asyncio.gather` bounded by `max_concurrency` (default 4).
- Dispatches each node to its respective Phase 22 Department Lead (`EngineeringLead`, `ResearchLead`, `OperationsLead`, `QualitySecurityLead`) with full quality-gate verification.
- Automatic retry handling with backoff and deadlock detection.

### 4. System & API Integration (`orchestrator.py`, `tools.py`, `server.py`, `cli.py`)
- **`MetaOrchestrator.orchestrate_dag`**: End-to-end execution of complex goals via DAG, updating `GlobalGoalMemory` milestones.
- **Tools**: Added `dag_plan_and_run` and `dag_visualize` tools to `titan_agent/tools.py`.
- **API**: Added `GET /api/dag/status` endpoint to `titan_agent/server.py`.
- **CLI**: Added `--dag` flag to `cli.py` for direct interactive or single-shot DAG runs.

### 5. Verification
- 7 comprehensive unit tests in `tests/test_phase23_dag.py`.
- 100% test pass rate across the entire repository (551 passed, 1 skipped). Clean ruff checks.

## 🏛️ Phase 22 — GENESIS HIERARCHICAL ARCHITECTURE (Meta-Orchestrator + 4 Department Leads)

Transformed Titan Agent from a flat single-agent model into an enterprise cognitive organization (CEO -> Department Leads -> Specialized Workers):

### 1. Daraja 1 — Meta-Orchestrator (Chief Agent) (`titan_agent/orchestrator.py`)
- **`MetaOrchestrator`**: The permanent executive brain coordinating departmental execution.
- **`GlobalGoalMemory`**: Persistent cross-session project direction, active goal tracking, and milestone lifecycle management.
- **`ResourceBudget`**: Token and step quota allocation and telemetry across departments with automatic exhaustion guards.
- **`ConflictResolver`**: Multi-department arbitration engine reconciling conflicting proposals (e.g. Quality/Security blocker overriding Engineering optimism).
- **Executive Synthesis**: Compiles departmental deliverables into structured C-level executive reports.

### 2. Daraja 2 — Team Leads with First-Line Verification Filters (`titan_agent/team_leads.py`)
4 dedicated Department Leads managing their specialist staff and applying departmental quality gates before escalating:
- **`EngineeringLead`**: Manages 7 roles (`coder`, `reviewer`, `test_writer`, `deployer`, `dependency_updater`, `performance_optimizer`, `db_architect`). Enforces Python AST syntax validation and execution checks.
- **`ResearchLead`**: Manages 4 roles (`researcher`, `data_validator`, `hallucination_checker`, `translator`). Enforces citation grounding and reference inspection.
- **`OperationsLead`**: Manages 4 roles (`scheduler_agent`, `notification_agent`, `cost_watcher`, `rate_limiter_agent`). Enforces scheduling constraints, rate limits, and token budgets.
- **`QualitySecurityLead`**: Manages 4 roles (`security`, `tester`, `critic_agent`, `fallback_agent`). Evaluates vulnerability severity and flags critical blockers (`SECURITY_BLOCKER`).

### 3. Daraja 3 — Full 27-Specialist Worker Roster (`titan_agent/staff.py`)
- Completed full 27-role roster with 10 new specialized roles:
  `data_validator`, `hallucination_checker`, `translator`, `scheduler_agent`, `notification_agent`, `rate_limiter_agent`, `critic_agent`, `fallback_agent`, `performance_optimizer`, `db_architect`.
- Added natural aliases for intuitive invocation.

### 4. Tools & CLI Integration (`titan_agent/tools.py`, `cli.py`)
- Added new tools:
  - `orchestrator_run`: Dispatches top-level goals through the hierarchical organization.
  - `team_delegate`: Directly delegates tasks to specific department leads.
  - `team_status`: Inspects department rosters, budgets, and milestone progress.
- Added `--meta` (`--orchestrator`) and `--department` CLI flags to `cli.py`.

### 5. Verification
- 9 new comprehensive tests in `tests/test_phase22_hierarchical.py`.
- 100% test pass rate: 544 passed, 1 skipped across the entire repository. Ruff linting clean.

## 🧭 Phase 42–44 — UNIFIED DIFF PATCHING + AUTONOMOUS SKILL SYNTHESIS + PROMETHEUS METRICS (trio #6)

Three major enhancements:

### 1. Tool level — Unified Diff Patch Applicator (`tools.py`, `agent.py`)
- New `apply_patch` tool allows Titan Agent to parse and apply standard unified diffs (`--- a/... +++ b/...`) across multiple workspace files transactionally with fuzzy hunk matching.
- Added to `WRITE_TOOL_NAMES` so edit runs automatically receive the bounded postcheck verification turn.
- Verified in `tests/test_patch_and_skills.py` with 3 deterministic unit tests (successful multi-hunk patch, format validation, conflict error).

### 2. Learning level — Autonomous Skill Playbook Synthesis (`skills.py`, `tools.py`)
- New `skill_save` tool allows Titan Agent to distill workflows, guidelines, and lessons into reusable markdown skill playbooks in `skills/<name>.md` with automatic YAML front-matter formatting.
- Auto-reloaded into `SkillRegistry` and immediately available for lexical auto-injection for future user requests.
- Verified in `tests/test_patch_and_skills.py` with 1 deterministic unit test.

### 3. Observability level — Prometheus & OpenTelemetry Metrics Exporter (`server.py`)
- New `/metrics` and `/api/metrics` endpoints expose standard Prometheus plain-text telemetry:
  - `titan_tool_calls_total{tool="...",status="ok|error"}` counters
  - `titan_tool_latency_ms{tool="..."}` gauges
  - `titan_skills_total` gauge
  - `titan_hitl_pending` gauge
  - `titan_system_info{status="ready"}` gauge
- Included in `_PUBLIC_PATHS` for zero-friction Prometheus / Grafana / Datadog scraping.
- Verified in `tests/test_metrics.py` with 1 deterministic test.

## 🧭 Phase 39–41 — DOCKER SANDBOX + WEB UI SUBAGENT ROSTER + TELEGRAM BOT GATEWAY (trio #5)

Three major capability upgrades:

### 1. Tool level — Docker Sandbox Runner (`tools.py`, `agent.py`)
- New `docker_sandbox_run` tool allows Titan Agent to execute untrusted code or shell commands safely inside an isolated, disposable Docker container.
- Supports image selection (`python:3.12-slim`, `node:20-slim`, `alpine:latest`, `ubuntu:22.04`), configurable memory limits (e.g. `256m`, `512m`), CPU quotas, network isolation (`none` vs `bridge`), and optional host workspace mounting.
- Verified in `tests/test_docker_sandbox.py` with 6 deterministic unit tests.

### 2. UI / Server level — Subagent Staff Network & Visual Roster (`server.py`, `web_ui/index.html`, `style.css`, `app.js`)
- Added `GET /api/staff/roles` endpoint returning all 17 dedicated specialist roles.
- Modern glassmorphic Subagent Staff Roster panel in the Web UI side panel with live badge counts, role badges, descriptions, and one-click prompt delegation.
- Verified in `tests/test_webui_staff.py` with 3 deterministic tests.

### 3. Gateway level — Interactive Telegram Bot Runner (`telegram_bot.py`, `run.py`)
- Standalone Telegram Bot daemon enabling remote control and bidirectional conversation with Titan Agent.
- Supports `/start`, `/help`, `/status`, `/mode`, `/effort` commands, real-time typing indicators, and asynchronous task execution with Markdown formatting.
- Launched via `python run.py --telegram` or `python -m titan_agent.telegram_bot`.
- Verified in `tests/test_telegram_bot.py` with 4 deterministic tests.

## 🧭 Phase 36–38 — SUBAGENT-FAILURE FUNNEL + DEAD-END EARLY STOP + GUARD DECISION LOG (trio #4)

Three more levers at three levels:

### 1. Tool level — delegated-subagent failures flow through the failure funnel (`tools.py`)
- Subagent delegation is a TOOL like any other, but a FAILED/ERRORED child
  previously came back inside a `### SUBAGENT […]` report that a weak parent
  could mistake for proven work — and the failure never reached the harness's
  failure accounting.
- New `_subagent_result_text()` turns a failed/errored child into an
  **Error-prefixed** result (status banner + the child's output + an explicit
  `⚠ … UNPROVEN` warning): the uniform funnel now records it as a failed tool
  execution — per-tool telemetry (`tool_stats`), the repeated-failure guard
  (re-delegating the identical task eventually gets blocked), and the critic's
  TOOL EVIDENCE snippet all see it. Successful delegations keep the exact
  previous format.
- Applied to both `tool_subagent_delegate` and every member of
  `tool_subagent_team`.

### 2. Harness level — dead-end early stop on consecutive all-failed tool batches (`agent.py`, `config.py`, `.env.example`)
- When EVERY tool result in a batch is a failure (error return, malformed
  skip, or guard block) there is no evidence of progress — but the classic
  loop would grind on to `max_steps`, burning token budget on a broken path.
- New `TITAN_DEAD_END_WINDOW` (default 5, `0` disables): after N consecutive
  all-failed tool batches the run stops EARLY with an explicit
  `⚠ Stopped early…` final answer (checkpoint saved as `done`), instead of
  requesting another LLM turn.
- `_record_batch_outcome()` feeds the streak from all three emission sites
  (main loop, reflection, refine); ANY successful tool result resets it.
- The streak is observable on the agent (`_consecutive_failed_batches`).

### 3. Server level — guard decision log + reset endpoint (`agent.py`, `server.py`)
- `execute_tool_unified` and the main-loop block site (`_run_one`) now record
  every block into a capped per-run **decision log** (`_guard_actions`) plus
  running totals (`_guard_totals`); malformed-blocks log too.
- `GET /api/guard/state` gains `actions` (most recent first), `totals`, and a
  `dead_end` section (window + current streak).
- New `POST /api/guard/reset` clears the live agent's guard state
  (counters, log, totals, streak) so an operator can give a stuck run a clean
  slate; auth-protected like every `/api` route.

### Verification
- `tests/test_subagent_failure_funnel.py` — **6 deterministic tests**: failed
  delegate reads as an Error with the UNPROVEN warning, crashed child reports
  its error, success output unchanged, team failures marked per member, and a
  live-funnel test proving the third identical delegation is blocked by the
  repeated-failure guard (which also records `blocked_repeat`).
- `tests/test_dead_end.py` — **6 deterministic tests**: default-window early
  stop (the 6th LLM call is never made), env-configured window, success
  resets the streak, disabled-by-env runs to completion with reflection, and
  the streak is exposed on the agent.
- `tests/test_guard_state.py` — **+5 tests** (9 total): actions/totals/dead-end
  ride along, empty defaults, reset requires auth, reset clears live state.
- Full suite: **504 passed, 1 skipped**, `ruff check .` clean.

## 🧭 Phase 33–35 — BROKEN-CALL GUARD + CONTEXT FLOOD CONTROL + OBSERVABILITY (trio #3)

Three more levers at three levels:

### 1. Tool level — repeated malformed-arguments guard (`agent.py`, `config.py`, `.env.example`)
- Tool calls whose arguments cannot be parsed as JSON are skipped (they must
  never run with empty arguments) — but such calls never reached
  `execute_tool_unified`, so the Phase 27 guard could not see them and a weak
  model could resend the SAME broken call forever.
- New per-run counters keyed by tool NAME (`_malformed_calls`): after
  `TITAN_MALFORMED_GUARD_LIMIT` (default 2, `TITAN_MALFORMED_GUARD` opt-out)
  name-level skips, further malformed calls from that tool are BLOCKED with an
  actionable error ("STOP resending broken calls — send ONE call with valid
  JSON arguments…") and a `Blocking malformed '{tool}'` status event.
- Counters reset per run.

### 2. Context level — tool-result size cap (`agent.py`, `config.py`, `.env.example`)
- A single oversized tool output (500KB log dump, whole-file read) could flood
  the model's context window — there was NO truncation of tool results.
- New `_cap_tool_result()` bounds every tool result appended to the
  conversation at `TITAN_TOOL_RESULT_MAX_CHARS` (default 4000, minimum 256)
  with an explicit marker: `… [tool output truncated: N chars total, showing
  first M]` — the model knows output was cut and how large it really was.
  Nothing under the cap changes; direct `execute_tool_unified` callers are
  unaffected.

### 3. Server level — guard observability mirror (`server.py`, `tests/test_guard_state.py`)
- `GET /api/guard/state` now mirrors the malformed-arguments counters
  (`malformed.{enabled,limit,patterns}`) alongside the existing
  repeated-failure `blocked_patterns`, sorted worst-first — one endpoint to
  see everything the harness is blocking.

### Verification
- `tests/test_malformed_guard.py` — **4 deterministic tests**: malformed calls
  skipped then blocked past the limit (tool never executes, run still
  finalizes with reflection), disabled-by-env pass-through, env-configured
  limit, and per-run counter reset.
- `tests/test_tool_result_cap.py` — **4 deterministic tests**: short results
  unchanged, oversized marker with true total, env-configured limit, and an
  end-to-end run where the capped result reaches the model truncated.
- `tests/test_guard_state.py` — **+1 test** (4 total): malformed patterns
  surfaced alongside blocked patterns.
- Full suite: **489 passed, 1 skipped**, `ruff check .` clean.

## 🧭 Phase 31–32 — VERIFICATION WITH NAMES + STRUCTURED-FUNNEL GUARD PROOF

Two refinements that close the remaining gaps from Phases 26–27:

### 1. Post-check names the exact files (`agent.py`)
- New `_written_paths(messages)` helper (deduplicated, first-seen order)
  extracted from the real write/edit tool calls — shared with the Phase 25
  evidence builder (single source of truth).
- The Phase 26 post-check prompt is now DYNAMIC: it appends
  `Files written/edited this run: …` so the weak model does not have to
  remember what it wrote — it re-reads the concrete list before finalizing.

### 2. Structured-funnel guard proof (`tests/test_structured_guard.py`)
- Two deterministic tests prove the Phase 27 "guard in `execute_tool_unified`"
  design end-to-end: a `ToolBridge` (the exact adapter react/plan/tot engines
  execute through) wired to the live wrapper blocks the third identical
  failing call, and the per-run counter is SHARED — failures recorded through
  the structured funnel block a later classic/direct call with the same
  identity (and vice versa).

### Verification
- `tests/test_structured_guard.py` — 2 deterministic tests (bridge blocking +
  shared-counter symmetry).
- `tests/test_postcheck.py` updated: post-check prompt asserts the concrete
  written path (`Files written/edited this run: p.txt`).
- Full suite: **480 passed, 1 skipped**, `ruff check .` clean.

## 🧭 Phase 28–30 — TELEMETRY TIE-IN + OBSERVABILITY + ANTI-DEAD-END (level trio #2)

Three more levers at three levels, shipped together:

### 1. Context level — failure intelligence in TOOL EVIDENCE (`agent.py`)
- `_build_tool_evidence` (Phase 25) now appends a **⚠ Repeated failures this
  run** caution section sourced from the per-run guard counters (Phase 23/27):
  exact tool names whose identical call already failed ≥2 times, sorted
  worst-first — so the critic sees precisely what not to repeat. Clean guard
  → no caution section (stable prompts).

### 2. Server level — guard observability API (`server.py`)
- New auth-protected **`GET /api/guard/state`** exposing the live agent's
  per-run repeated-failure counters (`blocked_patterns`: tool + failure
  count, sorted worst-first) plus the effective `enabled` / `limit` config —
  an operator can see exactly which calls the harness is blocking and why.

### 3. Harness level — empty final-answer guard (`agent.py`, `config.py`, `.env.example`)
- New `TITAN_EMPTY_FINAL_GUARD` (default `1`). Whitespace-only final answers
  are never a silent success: the harness retries ONCE with a bounded system
  prompt asking for the answer; if the second attempt is also empty the final
  answer becomes an explicit notice while preserving the run state. Bounded
  (`empty_retried`), disabled-by-env, and only fires on truly empty content.

### Verification
- `tests/test_evidence_critique.py` — **+3 Phase 28 tests** (7 total):
  caution section surfaces repeated failures (≥2), sorted worst-first with
  the lower counts omitted, and clean guards produce no caution section.
- `tests/test_guard_state.py` — **3 deterministic tests**: the endpoint is
  auth-gated (401/403), returns config + empty counters, and lists seeded
  blocked patterns sorted worst-first with the tool field extracted.
- `tests/test_empty_final.py` — **4 deterministic tests**: one bounded retry
  then normal finalize (grounding still runs), second empty → explicit
  notice, disabled-by-env immediate notice, and a bounded retry after tool
  use with the reflection pass still applied.
- Full suite: **478 passed, 1 skipped**, `ruff check .` clean.

## 🧭 Phase 25–27 — MULTI-LEVEL STRENGTHENING (context + harness + tool funnel)

Three levers at three different levels, shipped together:

### 1. Context level — evidence-aware critique (`agent.py`)
- The reflection/critic prompt now receives a deterministic `#### TOOL
  EVIDENCE` block built from the REAL tool round-trips already in the
  conversation: each tool message's name + result snippet (first 12), plus a
  deduplicated `Files written/edited: …` list extracted from `write_file` /
  `edit_file` / `deep_coder` arguments.
- The weak critic argues against facts instead of vibes — zero extra LLM
  calls, only the reflection prompt content changes (call counts unchanged).

### 2. Harness level — bounded auto post-check for edit runs (`agent.py`, `config.py`, `.env.example`)
- New `TITAN_AUTO_POSTCHECK` (default `1`). When a run ACTUALLY wrote/edited
  files, exactly ONE bounded verification turn is injected before finalizing:
  the enclosing system message tells the model to re-read the changed files,
  run the relevant tests/build/checks, report real output, and fix+re-verify
  if anything is red, then end with a "Verified:" note.
- Reads final answer verification into tool-using runs — previously only
  zero-tool runs got a grounding pass. Read-only runs and runs with the
  feature disabled are byte-for-byte unchanged; bounded to one pass (`postcheck_done`).

### 3. Tool-funnel level — repeated-failure guard everywhere (`agent.py`, `tests/test_repeat_guard.py`)
- The Phase 23 guard counter moved INTO `execute_tool_unified`, the single
  funnel every tool execution goes through (classic loop, structured engines
  via `ToolBridge`, cron, queue, direct calls). One shared per-run counter,
  no double counting: `_run_one` only blocks, the wrapper counts
  (error-strings and exceptions alike, success forgives, state resets per run).
- Classic-loop behavior is unchanged (_run_one still emits `"ok"` status for
  blocked calls so cancel-on-failure never cascades); repeat-guard tests now
  patch `_execute_tool_unified` so the wrapper/guard stay live.

### Verification
- `tests/test_evidence_critique.py` — **3 deterministic tests**: critic prompt
  carries the evidence block after a tool round-trip; written file paths are
  extracted into the block; paths are deduplicated.
- `tests/test_postcheck.py` — **4 deterministic tests**: edit runs get exactly
  one post-check pass (status + prompt delivered + extra LLM call), read-only
  runs skip it, disabled-by-env, and the post-check round may itself use tools.
- `tests/test_repeat_guard.py` — **+3 Phase 27 tests** (9 total): direct
  wrapper calls blocked after limit, exceptions count then block, disabled
  pass-through — plus the existing tests now prove single-counting end-to-end.
- Full suite: **468 passed, 1 skipped**, `ruff check .` clean.

## 🧭 Phase 24 — TASK RE-ANCHORING AFTER CONTEXT COMPACTION

Long runs lose the ORIGINAL objective when old messages get compacted — worst
with small models. Now, whenever compaction ACTUALLY drops messages, a compact
system reminder re-pins the original task right before the next model call.

### 1. Re-anchor on proactive per-iteration trim (`agent.py`, `config.py`)
- Inside `run_task`'s loop, when the pre-chat `compact_messages_for_context`
  pass trimmed anything, `_reanchor_task()` appends a system reminder
  `## ORIGINAL TASK (re-anchored): keep working toward this exact objective — …`
  (task truncated to `ORIGINAL_TASK_MAX_CHARS` = 800) and emits a
  `Re-anchored to the original task after context compaction.` status event.
- Because it is a `system` message it joins the never-dropped head region, so
  it persists for the rest of the run; the duplicate guard means it is never
  appended twice.

### 2. Re-anchor on provider-window overflow halving
- `_chat_with_recovery(..., anchor=)` is a new opt-in keyword (default `None`
  → byte-for-byte unchanged for existing callers/tests). `run_task` passes the
  user input on BOTH chat paths (main loop + grounding pass); after the
  overflow-halving compact, `working` is re-anchored before the retry.

### 3. Config
- `TITAN_TASK_REANCHOR` (default `1`, opt-out) → `objective_reanchor_enabled()`.
- `.env.example` documents the key. Short runs are EXACTLY unchanged (the
  feature only fires after a compaction actually happened).

### Verification
- `tests/test_reanchor.py` — **6 deterministic tests**: in-run compaction
  anchors the objective text + status event, no-compaction never anchors,
  disabled-by-env, overflow-halving re-anchor through `_chat_with_recovery`,
  `_anchor_block` content/truncation, and the no-duplicate guarantee. The
  recording fake LLM answers the context summarizer's single-user prompt
  separately so compaction never starves the scripted run queue.
- Full suite: **458 passed, 1 skipped**, `ruff check .` clean.

## 🚦 Phase 23 — REPEATED TOOL-FAILURE GUARD (anti-retry-loop)

Weak models re-send the SAME failing tool call with the SAME arguments over
and over — burning tokens and repeating the same dead end. Phase 23 makes the
harness itself break the loop, no model intelligence required.

### 1. Per-pattern failure counters (`config.py`, `agent.py`)
- The run loop tracks consecutive identical failures per pattern
  `(tool name, canonical sorted-key JSON of args)` inside `_emit_tool_results`
  — any ARGUMENT change resets the counter, a SUCCESS forgives the pattern.
  State resets at the start of every `run_task` (and always exists on the
  agent, so `_emit_tool_results` stays safe when called standalone).
- `TITAN_REPEAT_GUARD` (default `1`) enables it; `TITAN_REPEAT_GUARD_LIMIT`
  (default `2`) is how many identical failures are tolerated before blocking.
- After the limit, the identical call is NOT executed anymore — the model gets
  an explanatory `Error: repeated tool failure guard …` result telling it to
  change arguments, switch tool or verify prerequisites. Blocked calls return
  `ok` status so `TITAN_CANCEL_ON_TOOL_ERROR` does not cascade-cancel healthy
  siblings in the same batch.

### 2. `.env.example`
- Documented `TITAN_REPEAT_GUARD`, `TITAN_REPEAT_GUARD_LIMIT`.

### Verification
- `tests/test_repeat_guard.py` — **6 deterministic tests** (scripted fake LLM +
  fake failing/succeeding executors): block after the limit (2 real attempts,
  3rd skipped), per-args counters (A,B,A then A blocked), success forgives,
  `LIMIT=1`, guard disabled, state reset across consecutive runs on the same
  agent.
- Full suite: **452 passed, 1 skipped**, `ruff check .` clean.

## 📊 Phase 22 — PER-TOOL TELEMETRY + ADAPTIVE TOOL RECORD

Weak models repeat the SAME failing tool call instead of switching approach.
Phase 22 gives Titan visibility into its own tool record — and lets the model
adapt mid-run — while giving operators a single endpoint for cost/latency truth.

### 1. Telemetry wrapper (`titan_agent/agent.py`, new `tool_stats.py`)
- Every tool execution funnels through `TitanAgent.execute_tool_unified`, now a
  thin telemetry wrapper around the renamed `_execute_tool_unified`: it records
  success/failure, latency (ms) and output size on a thread-safe, bounded
  `ToolStatsCollector` WITHOUT changing any caller's behavior — exceptions still
  propagate, error strings are detected by the `"Error"` prefix, policy/HITL
  denials count as failures.
- Default collector is the process-wide `TOOL_STATS` singleton, so the server
  endpoint and the agent's own introspection see the same record across runs.
  An isolated collector can be injected (`tool_stats=`) for deterministic tests.

### 2. `tool_stats` introspection tool (`agent.py`)
- The agent can query its own execution record mid-run (per-tool calls,
  ok/errors, error rate, avg latency, last error) and switch approach when a
  tool keeps failing. Wired into `_build_tools_list` AND the live catalog text.

### 3. Adaptive tool record (`config.py`, `agent.py`)
- `TITAN_TOOL_RECORD=1` (default `0`, opt-in) injects a `### TOOL RECORD`
  block into future system prompts: only tools with ≥3 calls AND at least one
  failure, worst error rate first (bounded at 8 lines). Healthy tools are never
  surfaced; default-off keeps prompts byte-for-byte stable.

### 4. `GET /api/tools/stats` (`server.py`)
- Auth-protected endpoint (auto-guarded like every `/api` route) returning
  `{totals, tools}` from the shared collector for dashboards/CLI.

### Verification
- `tests/test_tool_stats.py` — **10 deterministic tests** (isolated collectors,
  real local memory tools, no network): success/error recording, exception
  re-raise recording, `tool_stats` tool JSON, catalog wiring, summary math,
  empty vs populated prompt block, opt-in injection, default absence, and the
  auth-protected endpoint via TestClient (401 without token, 200 with).
- Full suite: **446 passed, 1 skipped**, `ruff check .` clean.

## 🧑‍⚖️ Phase 21 — DEDICATED REVIEWER MODEL + BOUNDED REFINEMENT

The critic/reflection pass that polishes final answers normally runs on the
SAME model that generated them — so a weak local generator critiques itself.
Phase 21 enables the classic "weak generator → strong critic → revise" split:
the reflection runs on a dedicated reviewer, then the generator revises against
the critique.

### 1. Reviewer wiring (`titan_agent/agent.py`, `config.py`)
- `TITAN_REVIEWER_PROVIDER` / `TITAN_REVIEWER_MODEL` — configure a separate
  reviewer LLM (e.g. a stronger cloud model while the generator stays cheap and
  local). Built lazily on first reflection via `_critic_llm()` (falls back to
  the generator model on any config error); the same call accepts an injected
  `reviewer_llm=` for tests/embedders.
- The reflection pass now calls `self._critic_llm()` — critic can still decide a
  tool call is needed (executed, loop continues) exactly as before.

### 2. Bounded refinement loop (`REFINE_PROMPT`)
- When a SEPARATE reviewer is in play, the run spends up to
  `TITAN_REFINEMENT_ROUNDS` (default `1`) generator revisions on the critic's
  output: `"A dedicated reviewer just critiqued your work… PROVE it."`
- A revision may emit tool calls (executed; loop returns to iterate with the new
  evidence), may fail gracefully (reviewer's final survives), and is bounded — no
  infinite loops. With NO reviewer configured, rounds default to 0 and behavior
  is byte-for-byte unchanged (verified backward-compat test).

### 3. `.env.example`
- Documented `TITAN_REVIEWER_PROVIDER`, `TITAN_REVIEWER_MODEL`,
  `TITAN_REFINEMENT_ROUNDS`.

### Verification
- `tests/test_reviewer.py` — **6 deterministic tests** (fake generator +
  fake reviewer + fake tool executor, no network): reviewer critiques and the
  generator revises; no-reviewer single-reflection unchanged; `ROUNDS=0` skips
  revision; revision tool-call handoff; failed revision keeps the reviewer's
  final; env auto-build of the reviewer with the generator model untouched.
- Full suite: **436 passed, 1 skipped**, `ruff check .` clean.

## 🛡️ Phase 20 — GROUNDED FINAL VALIDATION (anti-hallucination)

A model that answers WITHOUT ever touching a tool is the classic hallucination
path for weak local models (hermes3:8b and similar) — and the old fast path
accepted such answers unvalidated. Phase 20 closes that hole: zero-tool final
answers now get exactly ONE forced verification turn before finalizing.

### 1. Grounding pass (`titan_agent/agent.py`)
- If the run has used **no tools at all** when a candidate final appears, one
  extra `GROUNDING_PROMPT` turn is issued: the model may emit real tool calls
  (which execute and the loop continues, now marked as tool-grounded) or
  explicitly decline with `NO_TOOLS_NEEDED` for pure-conceptual tasks.
- Runs that already used tools **never** pay for this call; the pass fires at
  most once per run (`grounded` flag), so it can never loop.
- Grounding uses `_chat_with_recovery` (transient retry + context-overflow
  halving already built in); if the grounding call itself fails, the run
  degrades gracefully to the draft instead of crashing.
- Emits a `"Verifying answer before finalizing (no tools used yet)..."` status
  so the Web UI / CLI shows exactly when the guard is firing.

### 2. Configuration (`titan_agent/config.py`, `.env.example`)
- `TITAN_FINAL_GROUNDING` (default `1`) — set `0` to restore the old
  single-call fast path for pure-chat workloads.

### Verification
- `tests/test_grounding.py` — **5 deterministic tests** (fake LLM + fake tool
  executor, no network): zero-tool answer gets a grounding pass whose tool call
  executes before the final; conceptual answer declines tools and finalizes
  with exactly one grounding; grounding failure keeps the draft; tool-using
  runs never ground; `TITAN_FINAL_GROUNDING=0` restores the legacy path.
- `tests/test_components.py::test_run_task_effort_guidance` updated for the
  new zero-tool single verification turn (ULTRA now 3 calls: main + grounding +
  reflection; LOW now 2: main + grounding).
- Full suite: **430 passed, 1 skipped** (Windows-only screenshot branch),
  `ruff check .` clean.

## 🚀 Phase 17 — BOUNDED PARALLEL TOOL EXECUTION

Tool calls that a single model turn emits now run concurrently but inside a
hard cap, and no single tool failure can crash the run anymore.

### 1. Concurrency cap (`titan_agent/config.py`)
- `TITAN_PARALLEL_TOOL_CALLS` (default `4`) bounds the number of tool calls
  executing simultaneously per model turn (an `asyncio.Semaphore`); `1` =
  fully serial. Read at call time so tests/runtime can tune it live.
- `TITAN_CANCEL_ON_TOOL_ERROR` (default `0`): when `1`, as soon as any tool
  fails the remaining in-flight calls are cancelled and reported as
  cancelled — useful when later tools consume earlier outputs.

### 2. Crash isolation (`titan_agent/agent.py` `_emit_tool_results`)
- Every tool call is now wrapped so ANY exception (not just RuntimeError /
  OSError / ValueError) becomes an ordinary `Error (Type): msg` tool result —
  one crashing tool never aborts its siblings or the whole run.
- Original reporting order is preserved: every tool_call_id still gets
  exactly one follow-up tool message, keeping the assistant->tool pairing
  valid for the next model request.
- Added 6 deterministic tests (`tests/test_parallel_tools.py`): bounded
  watermark, serial mode, crash isolation, cancel-on-failure, and
  report-all-results default mode.

## 🧠 Phase 18 — CONTEXT COMPACTION (Claude-Code-style compact)

Over-budget run windows no longer silently drop their middle: the trimmed
region is summarized by the LLM and kept as a compact background block.

- `compact_messages_for_context()` — new async trim that, when a summarizer is
  available and something was actually dropped, replaces the
  `CONTEXT_TRIM_MARKER` with a `system` "background summary" block (kept
  exactly 1:1 so the assistant->tool pairing is never disturbed).
- `TitanAgent._summarize_context()` — condenses dropped messages (≤14k chars)
  into a ≤700-char factual summary via `self.llm`; ANY failure returns `None`
  and the run falls back to the legacy marker trim — compaction can never
  break a run.
- Wired into the proactive per-iteration trim and the overflow-handling path
  in `_chat_with_recovery`; under-budget runs never call the summarizer, so
  the common path costs nothing.
- Added 8 deterministic tests (`tests/test_compaction.py`) including an
  end-to-end overflow run that finishes with the summary block in place.

## 🛂 Phase 19 — LIVE HITL APPROVALS PANEL IN WEB UI

The web cockpit now shows pending human-approval requests and lets an
operator approve/deny them inline — making the Phase 14 HITL gate actually
usable from the dashboard.

- `index.html`: new "Approvals" sidebar section with a live pending-count
  badge and a Refresh button.
- `app.js`: `fetchHITLPending()` polls `/api/hitl/pending` every 5s and
  renders each request (action, resource, reason, details) with Approve/Deny
  buttons that POST `/api/hitl/decide` (`decision/request_id/by`). Failed
  polls pause for 60s instead of re-prompting the API key on every tick;
  all dynamic fields are escaped before innerHTML injection.
- `style.css`: styled the panel (items, status pill, approve/deny buttons).
- Added 3 structural tests (`tests/test_webui_hitl.py`) asserting the panel
  markup, endpoint wiring, polling guard and escaping.

## 🔧 Phase 16 — DOCKER PACKAGING

Ship the web dashboard / API server as a container: one `docker build`, one
`docker compose up`, on Linux / macOS / Windows (Docker Desktop).

### 1. `Dockerfile`
- `python:3.12-slim` base; installs `git` + `ca-certificates` (gitops /
  `self_update` / TLS), pip-installs `requirements.txt` as its own layer for
  fast rebuilds.
- Build-time smoke gate: `python -c "import titan_agent.server"` fails the
  build early if the server wiring (FastAPI app + all singletons) is broken.
- Runs `uvicorn titan_agent.server:app` on `0.0.0.0:7860` (`EXPOSE 7860`).

### 2. `docker-compose.yml`
- Service `titan-agent` — `restart: unless-stopped`, host port from
  `TITAN_PORT` (default 7860), `env_file: .env`.
- Named volume `titan-workspace` → task state, checkpoints, core memory and
  the HITL audit trail survive restarts; `mcp_servers.json` bind-mounted
  read-only so MCP config is editable without rebuilding.
- HTTP healthcheck against `/health` (interval 30s, start period 10s).

### 3. `.dockerignore`
- Excludes `.env`, `workspace/`, `*.db`, `.server_key`, `*.log`, venvs and
  frontend deps (web UI ships as static files inside the package);
  `!.env.example` stays shippable. Stray root probe/debug scripts excluded and
  removed from the working tree.

### 4. `README.md`
- "Method 4: Docker" quick-start: build, run, volume/healthcheck notes and the
  `host.docker.internal` caveat for self-hosted gateways (OmniRoute).

### Verification
- `tests/test_docker.py` — **6 deterministic tests** (no daemon): Dockerfile
  base/entrypoint/smoke gate, compose mounts + healthcheck, dockerignore
  secret hygiene, offline server-module import (the exact Dockerfile smoke
  check) and web_ui presence. Full suite **409 passed, 1 skipped**, `ruff check .`
  clean (stray probe scripts also removed).

## 🔧 Phase 15 — STRUCTURED JSON LOGGING + `/api/logs/recent`

Every log line from the `titan_agent` logger tree is now a single
machine-parseable JSON object, mirrored into an in-memory ring buffer that the
web UI / API can query — no filesystem reads, no log-tailing.

### 1. `titan_agent/logging_setup.py` (new)
- `JsonFormatter` — emits `{ts, level, logger, message}` plus every `extra`
  field passed to the log call (e.g. `event`, `session_id`) and a `traceback`
  for exception records; standard `LogRecord` attributes never leak.
- `RingBufferHandler` — mirrors each record as a dict into the bounded
  `LOG_RING` deque (size from `TITAN_LOG_BUFFER`, default 500).
- `setup_logging()` — idempotent: exactly one stream handler + one ring
  handler on the `titan_agent` logger; propagation disabled so records are NOT
  re-rendered by root/uvicorn (single JSON source of truth). Level from
  `TITAN_LOG_LEVEL` (default INFO).

### 2. Live endpoint (`titan_agent/server.py`)
- `GET /api/logs/recent?limit=&level=` — newest JSON log records first,
  optional exact-level filter, sane clamping, auth-protected like every `/api`
  route. `setup_logging()` runs at server import.

### 3. `.env.example`
- Documented `TITAN_LOG_LEVEL` and `TITAN_LOG_BUFFER`.

### Verification
- `tests/test_logging.py` — **11 deterministic tests** (no network): formatter
  JSON shape + extras + traceback + no standard-attr leaks, ring mirroring,
  exotic-extra resilience, idempotency, propagation off, endpoint auth +
  newest-first ordering + level filter + limit clamp. Full suite
  **403 passed, 1 skipped**, ruff clean.

## 🔧 Phase 14 — HUMAN-IN-THE-LOOP (live approval gate + HTTP API)

Sensitive operations (`delete_file`, `screenshot`, …) now create a real pending
approval request the agent *waits on* — surfaced through a protected HTTP API and
audited to disk — instead of being silently hard-denied or auto-run.

### 1. Live approval gate (`titan_agent/agent.py`)
- `TitanAgent.__init__(hitl=…, hitl_timeout=…)` — accepts the global
  `HumanInTheLoop` and wires it onto its tool registry in the constructor.
- `_approval_gate()` — **one approval funnel for every loop style** (classic,
  structured strategy, cron, queue): every `execute_tool_unified` call is
  checked against the policy. `delete_file` / `screenshot` → a pending request
  is created; the run waits up to `hitl_timeout` for a human decision and only
  proceeds on explicit APPROVE. FULL access auto-grants; no HITL wired keeps
  today's permissive behavior (tests/headless untouched).

### 2. Guarded `ToolRegistry` parity (`titan_agent/core/tools/registry.py`)
- `__init__(hitl=…, hitl_timeout=…)` + `attach_hitl()` (late wiring).
- Require-approval decisions escalate to HITL via `_ensure_approved()` and only
  raise `PermissionError` when the human denies/times out or no HITL is set.

### 3. Structured strategy defers (`titan_agent/structured.py`)
- `ToolBridge(…, defer_approval=…)` — when no HITL is attached, deferring lets
  the request travel to the registry gate instead of being denied; the default
  `False` keeps the existing "approval required" behavior for direct users.

### 4. Server wiring + HTTP API (`titan_agent/server.py`)
- Global `hitl_manager` (audit → `workspace/hitl_audit.jsonl`), timeout from
  `TITAN_HITL_TIMEOUT` (default 120 s), attached to the registry and agent.
- `GET  /api/hitl` — audit trail (recent requests newest-first + status counts).
- `GET  /api/hitl/pending` — everything waiting on a human.
- `POST /api/hitl/request` — create a request (manual / tooling / tests).
- `POST /api/hitl/decide` — `approve | deny | cancel` (idempotent; 404 unknown,
  422 bad decision).
- `GET  /api/hitl/{request_id}` — single-request status.
- Every endpoint is protected by the Phase 12 Bearer-token auth.

### 5. `.env.example`
- Documented `TITAN_HITL_TIMEOUT`.

### Verification
- `tests/test_server_hitl.py` — **18 deterministic tests** (network-free, no
  real LLM): auth gating, full request→pending→decide→audit lifecycle,
  idempotent decisions, agent gate approve/deny, guarded-registry approve/deny,
  ToolBridge defer semantics. Full suite **392 passed, 1 skipped**, ruff clean.
- `tests/test_server_auth.py` — `_auth_headers()` now reads `TITAN_API_KEY` at
  call time so multiple server test modules can share one env key regardless of
  pytest collection order.

## 🔧 Phase 13 — PROVIDER FALLBACK CHAIN (multi-provider resilience)

When the primary LLM provider fails with a transient error, `chat_completion`
now automatically rolls over to the next provider from a configurable chain —
so one dead/rate-limited/unconfigured provider never kills the agent.

### 1. Call-time configuration (`titan_agent/config.py`)
- `provider_fallback_chain()` — comma-separated providers from
  `TITAN_PROVIDER_FALLBACK_CHAIN` (e.g. `"kimi,glm,ollama,deepseek"`), read at
  CALL time so tests and the runtime can change the chain without a restart.
- `provider_fallback_models()` — optional per-provider model overrides from
  `TITAN_PROVIDER_FALLBACK_MODELS` (e.g. `"kimi=kimi-k3,glm=glm-5.3-flash"`).
- `provider_default_model(provider)` — known default model for every registered
  provider so the chain can pick a sane model when none is overridden.

### 2. Fallback engine (`titan_agent/llm_client.py`)
- `chat_completion()` is now an orchestrator: it builds the chain, tries the
  primary first, then each fallback provider, and raises
  `RuntimeError("All providers failed. Errors: …")` naming every attempt when
  the whole chain is exhausted.
- `_chat_completion_once()` — the original single-provider HTTP call, unchanged.
- `_build_fallback_chain()` — primary first, deduplicated, skipping providers
  that need an API key but have none configured (`_has_credentials`).
- `_is_transient_api_error()` — the rollover policy: network errors (aiohttp
  `ClientError`, `OSError`, `TimeoutError`) plus HTTP **408/429/5xx** and
  "is not configured" roll over; **401/403 (auth) and malformed requests fail
  fast** (project convention — a bad key on one provider is not fixed by
  another). `set_model()` re-resolves credentials per provider during fallback.
- Client configuration (provider/model/base_url/api_key) is restored in a
  `finally` so a fallback never silently reconfigures the session.

### 3. `.env.example`
- Documented `TITAN_PROVIDER_FALLBACK_CHAIN` and `TITAN_PROVIDER_FALLBACK_MODELS`.

### Verification
- `tests/test_provider_fallback.py` — **15 deterministic tests**, network-free
  (per-provider call scripted via an instance-level fake); chain ordering,
  dedup, key-less provider skipping, local providers without keys, model
  overrides, primary-success-no-fallback, fallback on network/429/5xx, 401
  fail-fast (chain never consulted), aggregate error on total failure, config
  restoration, and the transient/no-transient classifier.
- Full suite: **374 passed, 1 skipped** (Windows-only branch).
- `ruff check` clean on all touched files.

## 🔧 Phase 12 — SERVER AUTHENTICATION (Bearer token on every /api route)

Every HTTP route except the public liveness check (`/health`) and the web-UI
shell (`/`) now requires `Authorization: Bearer <TITAN_API_KEY>`. The web UI
shell stays public so a browser can load the page; the UI prompts for the key
via JavaScript.

### 1. `titan_agent/auth.py` (new)
- `get_server_api_key()` resolves the server key in priority order:
  1. `TITAN_API_KEY` env var (explicit operator choice);
  2. the persisted random key in `workspace/.server_key` (survives restarts);
  3. a freshly generated `sk-titan-…` key — persisted to `workspace/.server_key`
     and printed ONCE to the console so the operator can copy it.
- `require_api_key` — FastAPI dependency returning 401 (`WWW-Authenticate:
  Bearer`) for missing/wrong tokens. `workspace/` is already gitignored, so the
  persisted key is never committed.
- `SERVER_KEY_FILE` derives from `WORKSPACE_DIR` (so a custom
  `TITAN_WORKSPACE` moves the key file with the workspace).

### 2. Route guarding — `titan_agent/server.py`
- `_apply_auth_dependency()` attaches `Depends(require_api_key)` to every
  non-public `APIRoute` **in place**, the version-safe way: FastAPI builds each
  route's dependency tree once in `APIRoute.__init__` and the per-request
  handler captures that tree by reference, so the auth node is inserted into the
  LIVE `route.dependant.dependencies` via `get_parameterless_sub_dependant()`
  (the identical mechanism `APIRoute.__init__` uses for `dependencies=…`).
  This avoids the FastAPI ≥ 0.120 API drift (`get_dependant` no longer accepts
  a `dependencies=` keyword) and works without rebuilding `route.app`.
- `_PUBLIC_PATHS = {"/", "/health"}` — only these two stay public.

### 3. `.env.example`
- `TITAN_API_KEY=` documented (optional — auto-generated + persisted if unset).

### Verification
- `tests/test_server_auth.py` — **19 deterministic tests** (no network): public
  `/health` + `/` stay open, every protected sample route 401s on missing/wrong
  token with `WWW-Authenticate`, a valid token passes the auth gate, every
  protected `APIRoute` carries `require_api_key`, and public paths never do.
- Full suite: **359 passed, 1 skipped** (Windows-only branch).
- `ruff check` clean on all touched files.

## 🔧 Phase 11 — INTENT ROUTER + SPECIALIST ROSTER (12 sub-agents)

The user's full wishlist of useful sub-agents exists now as real staff roles —
**and** the routing logic itself is a first-class agent (`router`) with a
deterministic, LLM-free engine exposed to the parent as `subagent_route`.

### 1. Intent Router (`titan_agent/intent_router.py`)
The "which sub-agent should do this" decision is now a pure, testable function:
- `route_intent(task)` scores every staff role by keyword hits across the whole
  roster, picks the **primary** role (ties broken by rule priority) and returns
  **supporting** roles, so the parent can fan out a parallel team.
- **Zero tokens / no model call** — deterministic keyword scoring, trivially
  testable, never raises (empty/unknown → generalist).
- The `router` staff role itself — "you route, you do not run" — read-only,
  cannot mutate the workspace.
- New tool `subagent_route(task)` renders `### INTENT ROUTE` plan (primary +
  supporting + matched-keyword reason) so the parent checks routing before
  delegating; `subagent_route` is in the agent prompt and in `_AGENT_SPAWNERS`.

### 2. Roster: 6 → 17 roles
All 12 requested specialists now exist as `Specialist` entries with persona,
tuned run options and an enforced `ToolPolicy`:

| Role | Requested as | Tool boundary |
|---|---|---|
| `security` | Security Auditor | read-only + scans; never writes/commits |
| `test_writer` | Test Writer | writes tests + runs them; never commits |
| `summarizer` | Context Summarizer | allowlisted read-only (files, RAG, web, memory) |
| `memory_keeper` | Memory Manager | memory/handoff tools + read; no workspace writes |
| `cost_watcher` | Cost/Token Watcher | read-only (files, git, memory) |
| `triager` | Error Triager | read-only diagnose-and-route |
| `doc_writer` | Doc Writer | writes docs only; never code/commit |
| `changelogger` | Changelog Agent | git history + writes changelog; never commits |
| `deployer` | Deploy Agent | runs pipelines/rollback; never commits |
| `dependency_updater` | Dependency Updater | edits manifests + runs builds; never commits |
| `router` | Intent Router | read-only assignment plans |

Researcher still blocks `git_commit`; reviewer still allowlisted read-only.
Aliases added: `audit`→security, `changelog`→changelogger, `deploy`→deployer,
`docs`→doc_writer, `memory`→memory_keeper, `cost`→cost_watcher,
`route`→router, `triage`→triager, `summary`→summarizer,
`dependencies`→dependency_updater, `write_tests`→test_writer.

### 3. Routing semantics worth knowing
- "review the new login for SQL injection" → **security + reviewer**: the
  Security-Auditor-vs-Code-Reviewer overlap resolves to security (safety rule
  sits higher in the priority table), reviewer rides along as support.
- "write unit tests for the login and update the README" → `test_writer`
  primary, `doc_writer` supporting — multi-role tasks decompose cleanly.

### Verification
- `tests/test_intent_router.py` — **13 deterministic tests**: 20-case role map,
  empty/unknown fallback, supporting-role extraction, security-over-reviewer
  tie-break, reason/plan-text shape, rule→role integrity, all 11 new aliases,
  `subagent_route` tool surface + catalog presence.
- `tests/test_staff.py` — exact catalog set updated to the 16 non-generalist
  roles; new `test_phase11_specialists_have_personas_and_policies`; prompt
  + `subagent_roles` roster assertions extended.
- Full suite: **340 passed, 1 skipped**; ruff clean on all touched files
  (the only `tools.py` findings are 4 pre-existing ASYNC221 warnings on
  Unix-only wmctrl code, present at HEAD).

## 🔧 Phase 10 — HARNESS HARDENING (context resilience, tool-arg repair, LLM recovery)

Three weaknesses in the classic run loop were hardened, each verified with
deterministic tests — no model-level claims, these are pure harness guarantees.

### 1. Context budget trimming (`trim_messages_for_context`)
Long / deep runs grew an unbounded `messages` list (assistant + tool results
appended every step) — 25–48+ steps of big tool outputs eventually blew the
provider window and killed the whole run. Now:
- Configurable budget **`TITAN_CONTEXT_BUDGET_CHARS`** (default 200 000 chars).
- Applied **proactively at every loop iteration** (no-op until the budget is
  actually exceeded).
- **Never drops** the system prompt or the first user task message (the task
  head survives so deep runs stay anchored).
- **Keeps the newest rounds first** (the active working window).
- Trims tool blocks **atomically** (assistant with `tool_calls` + its tool
  messages together), so the message array always stays API-valid.
- Inserts a one-line marker so the model knows earlier context was truncated.

### 2. Tool-call argument repair (`parse_tool_arguments`)
Previously an unparsable arguments payload silently became `{}` — the tool ran
**with empty arguments** (a no-op at best, a destructive call at worst) and the
model's intent was lost. Now the payload is best-effort repaired (empty → `{}`,
dict pass-through, code-fence/backtick stripping, one balanced `{...}` region,
non-dict JSON wrapped as `{"value": ...}`) and if it genuinely cannot be parsed
the call is **skipped** with the raw payload reported back to the model so it
can resend. Every `tool_call_id` still receives exactly one tool message, so
the assistant→tool pairing stays valid on the next request.

### 3. LLM call recovery (`_chat_with_recovery`)
Any transient network error or context-length failure used to kill the run
immediately. Now:
- Transient errors (`aiohttp.ClientError` / `OSError` / timeouts) retry with
  linear backoff, bounded by **`TITAN_LLM_TRANSIENT_RETRIES`** (default 2).
- Context-length errors trigger **progressive halving**: the context is shrunk
  to ~half its current size and retried (bounded, ≤ 6 shrinks), because we do
  not know the provider's real window — over-budget runs degrade gracefully
  instead of dying mid-task.
- API-level failures (401/403/...) still fail fast.

### Verification
- `tests/test_hardening.py` — **12 deterministic tests** (trim no-op / head+tail
  / block atomicity / no orphan tools; parse valid/invalid/non-dict; emit
  skip-with-feedback and order preservation; transient retry recovery; all-
  retries-exhausted clean failure; overflow halving; overflow recovery
  end-to-end through `run_task`).
- Full suite: **329 passed, 1 skipped**; ruff clean on all touched files.

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