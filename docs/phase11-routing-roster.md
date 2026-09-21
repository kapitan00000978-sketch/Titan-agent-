# Titan Agent — Phase 11: INTENT ROUTER + SPECIALIST ROSTER

Phase 9 built a staff of five named specialists (`planner`, `researcher`,
`coder`, `reviewer`, `tester`). Phase 11 does two things with one idea: the
**routing logic itself becomes an agent**, and the staff grows to **17 roles**
covering every sub-agent the user asked for (quality/safety, context/memory,
monitoring, docs, deploy, and the router itself).

The whole phase is **deterministic**: the routing engine is a pure keyword
scoring function with no model call, so it costs zero tokens and is trivially
testable. Nothing here depends on provider behaviour.

---

## 1. Intent Router — `titan_agent/intent_router.py`

### The idea
"Which sub-agent should handle this request?" is normally answered by the
parent model — a freeform, unverifiable judgement. In Phase 11 that decision
is a **first-class, LLM-free engine** (`route_intent`) that the parent can call
before delegating (`subagent_route` tool), and the `router` staff role uses it
as its persona: *you route, you do not run*.

### How it works
- `ROUTE_RULES` — an ordered table of (keywords, role). Order matters: earlier
  rules win ties, so urgent/specific roles (`security`, `changelogger`,
  `deployer`, …) sit above generic ones (`reviewer`, `planner`, `coder`).
- `route_intent(task)` → `IntentRoute`:
  - lowercases + strips the task;
  - scores every role by matched keyword hits;
  - **primary** = highest hit count, ties broken by rule priority;
  - **supporting** = the other matched roles (deduped, capped at 3) so the
    parent can fan out a parallel team;
  - empty / unknown input → `generalist` (never raises);
  - `reason` lists the matched keywords ("coder via 'implement'…") so the
    plan is auditable.

### The tool surface
`subagent_route(task)` (in `tools.py`, also registered in `_AGENT_SPAWNERS`
and mentioned in the agent system prompt) returns:

```
### INTENT ROUTE
Primary: security
Supporting: reviewer
Reason: Matched keywords: security via 'sql injection', reviewer via 'review'.
```

### Notable routing semantics
- **Security vs Code Reviewer overlap** (the user's exact scenario):
  `"review the new login for SQL injection"` → primary **security**,
  supporting **reviewer**. The safety rule is earlier in the table, so the
  Security Auditor wins the tie and the reviewer rides along.
- **Multi-role decomposition**:
  `"write unit tests for the login and update the README"` → primary
  **test_writer**, supporting **doc_writer**.
- **Singular/plural handled:** both `dependency` and `dependencies` are
  keyword entries (the earlier naive table missed the plural).

---

## 2. Roster: 6 → 17 roles

Every requested sub-agent now exists as a `Specialist` with a persona, tuned
run options and an enforced `ToolPolicy`:

| Role | Requested as | Tool boundary |
|---|---|---|
| `security` | Security Auditor | read-only + scanners; never writes/commits |
| `test_writer` | Test Writer | writes & runs tests; never commits |
| `summarizer` | Context Summarizer | allowlisted read-only (files, RAG, web, memory) |
| `memory_keeper` | Memory Manager | memory/handoff tools + read; no workspace writes |
| `cost_watcher` | Cost/Token Watcher | read-only (files, git, memory) |
| `triager` | Error Triager | read-only diagnose-and-route |
| `doc_writer` | Doc Writer | writes documentation only; never code/commit |
| `changelogger` | Changelog Agent | git history + writes changelog; never commits |
| `deployer` | Deploy Agent | runs pipelines / rollbacks; never commits |
| `dependency_updater` | Dependency Updater | edits manifests + runs builds; never commits |
| `router` | Intent Router | read-only assignment plans |

Design rules applied consistently:
- **Read-only roles carry an allowlist** (`allowed_tools is not None`) so a
  summarizer or cost watcher physically cannot touch the workspace.
- **Writers-of-docs/tests may write files but never commit** (`git_commit`
  blocked) — the changelogger cannot commit its own changelog, by design.
- The router blocks all write tools and all `_AGENT_SPAWNERS` (no nesting).

Aliases added so the parent can write the obvious word and land correctly:
`audit`→security, `changelog`→changelogger, `deploy`→deployer, `docs`→doc_writer,
`memory`→memory_keeper, `cost`→cost_watcher, `route`→router, `triage`→triager,
`summary`→summarizer, `dependencies`→dependency_updater, `write_tests`→test_writer.
The existing `auditor`→reviewer alias is untouched.

---

## 3. Verification

- `tests/test_intent_router.py` — **13 deterministic tests**:
  20-case primary-role map (every new role + the Phase 9 core),
  empty/unknown fallback, supporting-role extraction, security-over-reviewer
  tie-break, reason/plan-text shape, `IntentRoute` frozen shape, rule→roster
  integrity, all 11 new aliases, `subagent_route` tool surface + schema
  presence in the catalog.
- `tests/test_staff.py` — the exact catalog set was updated to the 16
  non-generalist roles; new `test_phase11_specialists_have_personas_and_policies`
  checks personas and the boundary rules in the table above; `subagent_roles`
  and agent-prompt assertions extended with all new role ids.
- Full suite: **340 passed, 1 skipped** (329 from Phase 10 + 11 new).
- `ruff` clean on all touched files. The only `tools.py` findings are **4
  pre-existing ASYNC221 warnings** on Unix-only wmctrl window-control code —
  present at HEAD, untouched by this phase.