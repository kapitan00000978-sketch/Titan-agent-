# Titan Agent — Phase 4: Git-First Workflow + Core Memory in the Live Loop

Phase 4 closes the two biggest remaining gaps against the 2026 comparison set:
**Aider's git-first auto-commit** and the **MemGPT/Mem0-style episodic memory**
that Devin / Claude Code use to carry experience across sessions.

## 1. Git tools (Aider-style) — `titan_agent/gitops.py`

Three new tools are registered on every agent run and listed in the live tool
catalog, so the model itself can run Aider's loop: inspect → edit → commit.

| tool | behaviour |
|---|---|
| `git_status` | working-tree state (`git status --short`) or `(working tree clean)` |
| `git_diff` | uncommitted changes (`diff --stat`); shows untracked files too |
| `git_commit(message)` | `git add -A` + `git commit -m`; repo-local author fallback |

Safety properties:

- **Repo-local identity only** — if the repo has no `user.name`/`user.email`,
  gitops sets **repo-local** `Titan Agent <titan@localhost>` (`TITAN_GIT_NAME` /
  `TITAN_GIT_EMAIL` to override). Global config is never read-modified, and an
  existing global identity is never clobbered.
- **Fail-soft** — "not a git repository" is a friendly string; `git_commit` on an
  empty tree returns `(nothing to commit — working tree clean)`.
- **Non-blocking dispatch** — blocking git calls run through `asyncio.to_thread`
  inside the async tool dispatcher, so SSE/CLI streaming never stalls.

```python
from titan_agent.gitops import auto_commit, git_commit, git_diff, git_status, find_repo_root

find_repo_root("C:/repo/src")          # -> C:/repo   (walks up for .git)
git_status("C:/repo")                  # -> "?? build.txt"
git_commit("C:/repo", "feat: build")   # -> "Committed: feat: build"
```

## 2. Auto-commit at end of run

`TitanAgent.run_task(..., auto_commit=True)` commits workspace changes after a
successful run with a subject derived from the task (`agent: <first 72 chars>`).

```python
agent = TitanAgent(auto_commit=True, git_root="C:/repo")   # or TITAN_GIT_AUTO_COMMIT=1
agent.run_task("fix the build script", session_id="web")
# -> after final_answer: git commit "agent: fix the build script"
```

Plumbed everywhere: `headless.py --auto-commit`, `ChatRequest.auto_commit`
(SSE), and the cron runner.

## 3. Episodic core memory in the live loop

`core/memory` `MemorySystem` (episodic/semantic/procedural with scoring and
consolidation) is now wired into `TitanAgent`:

- **Lazy open** — construction never touches disk; the store opens on first use
  at `workspace/core_memory.db` (gitignored) or `core_memory_path=...`.
- **Write** — `_finalize_run` records an episodic memory for every completed run
  (classic loop and all structured strategies): task, result, mode, strategy,
  session.
- **Read** — `_core_recall_block` injects relevant past runs/lessons into the
  system prompt before each run (both classic and structured paths), but only
  when records exist — fresh stores leave prompts byte-identical, so all
  existing behaviour and tests are preserved.

```python
agent = TitanAgent(core_memory_path="data/core.db")
async for ev in agent.run_task("fix the login flow", mode="fast"):
    ...
# Next session: agent._core_recall_block("login flow") returns past-run truth.
```

## 4. Files

| file | change |
|---|---|
| `titan_agent/gitops.py` | **new** — git primitives + auto-commit |
| `titan_agent/agent.py` | `git_*` tools + dispatch; `core_memory` / `git_root` / `auto_commit`; `_finalize_run` + `_core_recall_block` |
| `titan_agent/headless.py` | `--auto-commit` flag + pass-through |
| `titan_agent/server.py` | `ChatRequest.auto_commit` + cron pass-through |
| `tests/test_phase4_gitops.py` | **new** — 15 tests (real `git init`/commit in tmp repos) |
| `CHANGES.md` | Phase 4 section |

## Verified

- `python -m pytest tests -q` → **208 passed** (193 + 15)
- `python -m ruff check` on all changed files → **All checks passed**
- End-to-end: headless import, `ChatRequest.auto_commit`, agent import, and a
  real temp-repo auto-commit run (`git init` → dirty file → `run_task` →
  commit exists, tree clean).