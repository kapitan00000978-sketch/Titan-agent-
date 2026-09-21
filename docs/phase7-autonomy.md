# Titan Agent — Phase 7: Full Autonomy

Phase 7 makes Titan **completely independent**: it stops, repairs and retries
on its own, can run without a human at the keyboard (task queue + daemon),
executes real-world actions (downloads, HTTP serving, screenshots, self-update)
and decomposes huge jobs across deep subagents.

No safety guardrail was removed — this phase raises **capability/length limits**
and adds self-service machinery, while the PolicyEngine, consent gates and SSRF
protections all stay active.

---

## Block A — Self-healing loop (`titan_agent/heal.py`)

When a command fails, Titan no longer stops and asks: it **diagnoses** the error,
applies the cheapest deterministic repair and **re-runs** the command until it
succeeds or the attempt budget is spent.

| Detected failure | Repair |
|---|---|
| `ModuleNotFoundError: No module named 'X'` | `pip install X` (or `--upgrade numpy` for `numpy.core` imports), then re-run |
| `numpy.core.multiarray` import error | upgrade numpy |
| cmdlet/command not found, `No such file`, `MemoryError` | one transparent retry |

- `diagnose(stderr, stdout) -> Repair | None` — pure classification function.
- `heal_run(run, command, max_attempts) -> HealResult` — the loop itself;
  `run` is an injected async `command -> (code, stdout, stderr)` so tests are
  fully deterministic (no subprocess, no LLM).
- `SelfHealEngine` — object wrapper used by the `self_heal` tool.
- All repairs run **locally**: zero LLM tokens for common failures.

## Block B — Dynamic step budget (`titan_agent/config.py`, `agent.py`)

The hard-coded 48-step clamp is gone; the budget is now configurable (and can be
disabled entirely):

| Env var | Default | Meaning |
|---|---|---|
| `TITAN_STEP_CAP` | `48` | ceiling applied after effort scaling (was hardcoded) |
| `TITAN_UNLIMITED_STEPS` | `0` | `1`/`true` removes the ceiling — Titan keeps iterating until the task is provably done |
| `TITAN_DEEP_MAX_STEPS` | `40` | deep modes' extra budget base (was hardcoded) |

`_compute_max_steps` still scales with mode/effort; `UNLIMITED_STEPS` just skips
the final clamp. The agent must still VERIFY and produce a final answer — having
more steps never bypasses verification.

## Block C — Task queue + daemon (`titan_agent/queue.py`, `daemon.py`)

A persistent, thread-safe **SQLite task queue** lets anyone (user, another agent,
a cron job, the web API) drop work for Titan and walk away:

- `enqueue(task, name, priority, schedule_at, max_attempts)` — priorities run
  first; `schedule_at` supports future scheduling.
- `claim_next()` — atomically claims the highest-priority *due* task (moves to
  `running` so parallel workers never double-run).
- `complete(task_id, result)` / `fail(task_id, error)` — failures retry with
  exponential backoff (5s → 15s → 30s → 60s) until `max_attempts` is spent.
- `list / get / stats / cancel / clear`.

The **daemon** polls the queue and runs tasks to completion with no human:

```
python -m titan_agent.daemon                      # loop forever (Ctrl+C to stop)
python -m titan_agent.daemon --once               # process all due tasks, exit
python -m titan_agent.daemon --poll 2 --concurrency 2
python -m titan_agent.daemon --list | --stats     # inspect the queue
```

Each task runs through the headless runner in a worker thread
(`asyncio.to_thread`), so the daemon's event loop and `run_headless`'s internal
`asyncio.run` never conflict. A crash on one task never kills the daemon.

## Block D — Real-world tools (`titan_agent/tools.py`)

New tools exposed to the LLM (auto-dispatched via `ToolRegistry`):

| Tool | What it does |
|---|---|
| `self_heal` | self-healing command runner (Block A) |
| `download_file` | SSRF-guarded download of a public http(s) file into the workspace (100 MB cap, private/loopback targets refused) |
| `start_http_server` / `stop_http_server` | serve the workspace (or any dir) over local HTTP in a background thread |
| `take_screenshot` | capture the primary screen to PNG (Windows, PowerShell, zero extra deps) |
| `self_update` | `git pull` (walk-up to repo root) + `pip install -r requirements.txt` + `pytest` |
| `task_enqueue` / `task_list` / `task_stats` / `task_cancel` | drive the autonomous task queue from inside the agent |
| `subagent_delegate` / `subagent_team` | deep subagent execution (Block E) |

## Block E — Deep subagent architecture (`titan_agent/subagents.py`)

A supervisor layer: a parent Titan delegates sub-problems to **independent child
agents** and collects their answers.

- Every child runs the headless runner with its **own session id**
  (`sub-<parent>-<n>`), so checkpoints/memories/session state never collide.
- `SubagentPool.delegate(task, ...)` — one child, block until result.
- `SubagentPool.team(tasks, ...)` — fan out N independent tasks in parallel,
  bounded by `max_workers` so the parent's LLM budget isn't thrashed.
- Sub-agents execute in worker threads; the parent needs the result before
  continuing, unlike the fire-and-forget daemon.

## API + CLI

Web API (mirrors the cron endpoints):

| Method | Path | Meaning |
|---|---|---|
| GET | `/api/queue/tasks?status=&limit=` | list + queue stats |
| POST | `/api/queue/tasks` | enqueue (`task`, `name`, `priority`, `schedule_at`, `max_attempts`) |
| DELETE | `/api/queue/tasks/{task_id}` | cancel a pending task |
| POST | `/api/queue/process-once` | run the daemon loop once inline (via the live agent) |

CLI (`cli.py`):

```
/queue list            /queue stats
/queue add <task>      /queue cancel <id>
/daemon                # run the daemon loop until Ctrl+C
```

## Tests

`tests/test_phase7_autonomy.py` (31 tests) — heal diagnostics + loop, dynamic
step budget, queue lifecycle (priority, scheduling, retries, backoff), daemon
run-once with an injected fake runner, subagent delegation/teams with a fake
runner, tool registration, download SSRF guard, HTTP server start/stop, and the
system-prompt catalog. **Full suite: 256 passed** (was 225).

`ruff` on `titan_agent/`: clean except the 4 known intentional `ASYNC221`
wmctrl warnings that predate this phase.

---

## Try it

```bash
# 1. Enqueue two jobs, give one higher priority
python -m titan_agent.daemon --list
titan> /queue add "Summarize CHANGES.md"
titan> /queue add "Review titan_agent/titan_agent/core"  # via priority

# 2. Run them to completion right now
python -m titan_agent.daemon --once

# 3. Or let the daemon poll indefinitely
python -m titan_agent.daemon --poll 5
```