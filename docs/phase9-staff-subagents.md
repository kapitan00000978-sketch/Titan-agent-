# Titan Agent — Phase 9: DEDICATED SUBAGENT STAFF

Phase 7 gave Titan a generic `SubagentPool` — every child was the same agent
with the same tools. Phase 9 gives Titan a **staff of named specialists**: each
subagent now has a real role with its own persona, tuned run options and an
**enforced tool policy**. A `researcher` cannot commit code, a `reviewer`
cannot rewrite files, a `coder` implements in the workspace — the parent
delegates each sub-task to the right expert instead of cloning itself.

## The roster

| Role | Persona | Run tuning | Tool policy |
|---|---|---|---|
| `generalist` | (none — identical to Phase 7) | `fast` / `auto` / `auto` | unrestricted |
| `planner` | Strategic Planner — decomposes goals into ordered, dependency-aware plans; never executes | `fast` / `high` / `plan` | unrestricted |
| `researcher` | read-only fact-gatherer: web/deep-search, file reads, RAG, sources | `deep_search` / `high` / `auto` | blocked: write/delete/commit, http server, screenshot, subagent spawners |
| `coder` | implement/fix/refactor with real tools, verify, commit | `fast` / `high` / `auto` | blocked: telegram writes |
| `reviewer` | read-only critic: bugs, edge cases, security, verdict | `fast` / `high` / `react` | allowed: only read/git-status/search/execute_command |
| `tester` | empirical verifier: run tests/commands, PASS/FAIL verdicts | `fast` / `high` / `auto` | blocked: write/delete/commit, http server, telegram, spawners |

Roles are resolved case-insensitively **with aliases** — `code`/`developer`,
`research`, `plan`, `review`/`critic`, `test`/`qa` all land on the right
specialist. Unknown roles fall back to `generalist` (never an error).

## How it works

```
parent Titan ── subagent_delegate(task, role="coder")
                         │
              StaffPool.run(role, task)
                         │  spec = get_specialist(role)
                         │  policy = ToolPolicy(spec.allowed_tools, spec.blocked_tools)
                         │  agent  = build_agent(tool_policy=policy)
                         ▼
        headless.run_headless(task, mode/effort/strategy from spec,
                              agent=agent, system_extra=spec.persona)
```

Three enforcement layers keep a role honest (not just "please behave"):

1. **Persona overlay** — `system_extra` is appended right after the base
   identity in the child's system prompt (`run_task(..., system_extra=...)`).
2. **Catalog filter** — `_build_tools_list()` / `_build_tool_catalog_text()`
   drop every tool a role may not use, so the child's model never even *sees*
   the forbidden tools (terminal, memory, skill, telegram, git and MCP alike).
3. **Execution gate** — `execute_tool_unified()` refuses any tool outside the
   role policy *before* dispatch, for **every** tool family. This is
   enforcement, not suggestion: even if the model invents a call, the child
   agent returns `Error: tool 'X' is outside this subagent's role...`.

`ToolPolicy` semantics: `allowed=None` → everything except `blocked`;
a non-None `allowed` set → only those tools (blocked still applies).

## Tools exposed to the parent

| Tool | Purpose |
|---|---|
| `subagent_roles` | Lists the roster (`id: title — description`) so the parent can pick the right specialist first. |
| `subagent_delegate(task, role, label)` | Runs one sub-task with a named specialist (default `generalist`), fresh session `sub-<parent>-<role>`. |
| `subagent_team(tasks, roles)` | Fans out parallel sub-tasks; `roles` is parallel to `tasks` (missing roles default to `generalist`). Parallelism bound: 2, or 8 in Phase 8 FULL ACCESS. |

The system prompt's subagent section now tells the model these roles exist and
how to pick them.

## Files touched

- **`titan_agent/staff.py` (new)** — `ToolPolicy`, `Specialist`, `SPECIALISTS`
  roster, `get_specialist()`, `staff_catalog()`, `StaffPool` (`run` / `team`
  with injectable runner for deterministic tests).
- **`titan_agent/headless.py`** — `run_headless(..., system_extra=)`;
  `build_agent(tools=None, tool_policy=None)`.
- **`titan_agent/agent.py`** — `tool_policy` on `TitanAgent`; `_policy_allows()`
  gate in `execute_tool_unified`; catalog/tool-list filtering; `system_extra`
  on `run_task`; system-prompt updates.
- **`titan_agent/tools.py`** — `subagent_delegate` gains `role`,
  `subagent_team` gains `roles`, new `subagent_roles` tool + handlers.

## Verification

- `tests/test_staff.py` — **26 deterministic tests** (no LLM/network): roster
  integrity, alias resolution, `ToolPolicy` filtering + enforcement, agent
  catalog filter, `execute_tool_unified` role blocking, `StaffPool` `run`/`team`
  semantics with an injected runner (session ids, role resolution, error
  reporting, ordering), catalog surface, and schema params.
- Full suite: **314 passed, 1 skipped**.
- `ruff check` clean on all touched files (only the 4 pre-existing `ASYNC221`
  wmctrl warnings remain in the wider tree).