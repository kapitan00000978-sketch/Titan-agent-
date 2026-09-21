# Titan Agent — Phase 5: Devin-Style Checkpoints & Resume

Phase 5 brings the continuity that defines long-horizon autonomy: **Devin's
checkpointed sessions** and **Claude Code's `--continue`/`--resume`**. A Titan
session that is interrupted (server restart, network blip, max steps, user
navigates away) can be resumed from the exact state it stopped at — nothing is
re-run from scratch.

## 1. Checkpoint store — `titan_agent/checkpoint.py`

`CheckpointStore` is a SQLite-backed store (one row per `session_id`) with the
same Windows file-lock-safety pattern as `core/memory`:

| API | behaviour |
|---|---|
| `save(RunCheckpoint)` | upsert — replaces any existing checkpoint for the session |
| `load(session_id)` | `RunCheckpoint \| None` |
| `list(limit)` | newest-first (updated_at, then rowid) |
| `delete(session_id)` | removes + returns `bool` |
| `stats()` | `{total, done}` |

A `RunCheckpoint` captures the run's live state: session, task, mode/effort/
strategy, the **conversation messages** (trimmed to the last 40), steps done,
tools used, status (`running | done | error`) and the final answer.

## 2. Always-on checkpointing in `run_task`

Checkpointing is **always on** — no flag required, exactly like a real Devin
session:

1. **Run start** — a `running` checkpoint is persisted.
2. **After every tool step** — messages + step count + tools used are saved
   (both the main loop and the reflection pass).
3. **On error** — status flips to `error` with the state preserved.
4. **On completion** — status `done` with the final answer, for classic and
   structured (`plan`/`react`/`tot`) runs alike.

Because every step lands in SQLite, an interruption can never lose the work done
so far.

## 3. Resume — `run_task(..., resume=True)`

- **Completed session?** If the checkpoint is `done` with a saved answer, the
  run returns that answer immediately (**no LLM call at all**) and emits a
  `status` event — cheap replays, no re-computation.
- **Interrupted session?** The saved conversation (system prompt + history +
  progress so far) is restored into the classic loop, a
  `Resuming session 'X' from checkpoint (N steps done, last status: ...)` event
  is emitted, and the loop continues from exactly where it stopped.
- **No checkpoint?** `resume=True` behaves like a normal run — zero impact.

Structured strategies re-plan on resume (their engines hold state in memory);
the checkpointed classic loop is restored verbatim. This is documented honestly
rather than faked.

## 4. Plumbing

| surface | change |
|---|---|
| `headless.py` | `python -m titan_agent.headless "task" --resume` |
| `run_headless(...)` | `resume: bool \| None` pass-through |
| `server.py` | `ChatRequest.resume` (SSE) + cron runner |

```bash
# run a job headlessly, let it checkpoint itself…
python -m titan_agent.headless "refactor payments" --session-id job1

# …interrupt it, then continue exactly where it stopped:
python -m titan_agent.headless "refactor payments" --session-id job1 --resume
```

## 5. Files

| file | change |
|---|---|
| `titan_agent/checkpoint.py` | **new** — `RunCheckpoint` + `CheckpointStore` |
| `titan_agent/agent.py` | always-on save/update/done/error; `resume` param; done-session replay; resume restore |
| `titan_agent/headless.py` | `--resume` flag + pass-through |
| `titan_agent/server.py` | `ChatRequest.resume` + cron pass-through |
| `tests/test_phase5_checkpoint.py` | **new** — 12 tests |
| `CHANGES.md` | Phase 5 section |

## Verified

- `python -m pytest tests -q` → **220 passed** (208 + 12)
- `python -m ruff check` on all changed files → **All checks passed**
- End-to-end proof: LLM crashes mid-run → `error` checkpoint → resume with a
  healthy LLM → original task restored into context → `done` with final answer
  (real crash→resume→done, verified by script).