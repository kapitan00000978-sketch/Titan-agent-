# Titan Agent — Phase 8: FULL ACCESS

Phase 8 is the "chegaralarni buz" (break the boundaries) completion: when Full
Access is enabled, **every limit that was ever placed on Titan is removed**.
Normal-mode behaviour stays byte-for-byte unchanged — the boundaries remain
configurable, and Full Access simply switches them off.

There are two access levels:

| Level | Env var | What it removes |
|---|---|---|
| `full` | `TITAN_FULL_ACCESS=1` | All **capability/comfort** boundaries (steps, timeouts, approvals, file-size caps, port range, rate limits, structured clamp, subagent bound) |
| `absolute` | `TITAN_ABSOLUTE_ACCESS=1` | Additionally the **last two protection lines**: destructive-command denies and the SSRF private-network guard. Implies `full`. |

Full Access is explicit and auditable: the system prompt tells the model the
boundaries are gone, `/api/config` reports the live state, and a runtime
`set_full_access()` toggle applies mid-run without a restart.

---

## What FULL_ACCESS removes (all of it)

### 1. Step budget (`agent.py` — `_compute_max_steps`)

Normal:

- base = `MAX_ITERATIONS` (25), deep modes scale it
- effort multiplier (low 0.5 / medium 1.0 / high 1.6 / ultra 2.0)
- ceiling `MAX_STEPS_CAP` (48), removable via `TITAN_UNLIMITED_STEPS`

Full Access: **no ceiling** plus a **4× larger budget** (`base * multiplier * 4`)
— the agent iterates until the task is verifiably done. It still must VERIFY
with tools and produce a final answer; having unlimited steps never bypasses
verification.

### 2. Command / process timeouts (`tools.py` — `_command_timeout`, `_run_command_raw`)

- `execute_command`: 45s → **10 minutes**
- `self_heal` raw runner default: 60s → 10 minutes (explicit larger timeouts on
  `self_update` are left alone)
- The timeout is selected at call-time, so a runtime toggle applies immediately.

### 3. Approval gates (`core/guardrails/policy.py`, `structured.py`, `core/tools/registry.py`)

`PolicyEngine.check()` / `checks()` take an `access` argument:

| access | `require_approval` rules | `deny` rules | prompt-injection blocks |
|---|---|---|---|
| `normal` | enforced | enforced | enforced |
| `full` | **auto-granted** (→ ALLOW) | enforced | enforced |
| `absolute` | auto-granted | **lifted** (→ ALLOW) | enforced |

- `ToolBridge` (structured path): `auto_approve` derives from config — every
  approval rule (delete_file / screenshot) passes without a human.
- Guarded `ToolRegistry`: same access-aware policy; the workspace-sandbox path
  rewrite is also lifted in Full Access (the agent may touch any path it can
  reach).
- Prompt-injection phrase blocking **never** lifts — it protects the model, not
  the host.

### 4. Structured-reasoning clamp (`structured.py` — `_build_config`)

The core engines clamp `max_steps` to 30. In Full Access the clamp rises to
1000 so `plan` / `react` / `tot` deep runs also keep working until done.

### 5. Downloads (`tools.py` — `download_file`)

| Limit | normal | full | absolute |
|---|---|---|---|
| scheme | http(s) only | http(s) only | any scheme `urlopen` supports |
| SSRF private/loopback guard | enforced | enforced | **lifted** |
| size cap | 100 MB | **2 GB** | 2 GB |
| fetch timeout | 30s | **2 min** | 2 min |

### 6. HTTP server ports (`tools.py` — `start_http_server`)

Normal: `1024–49151` → Full Access: **any valid port `1–65535`**.

### 7. Token rate-limiter (`token_limit.py`)

`TokenRateLimiter` is constructed with `disabled` derived from config, and
`acquire()` checks the live flag at call-time — throttling returns 0 waits.
`stats()` reports `disabled` so `/api/token-usage` shows the real state.

### 8. Subagent parallelism (`tools.py` — `subagent_team`)

Worker bound raised **2 → 8** (`_subagent_worker_cap()`).

### 9. Model awareness (`agent.py` — system prompt)

While Full Access is on, `run_task` appends a **FULL ACCESS MODE ACTIVE** block:
no step budget, no 45s timeout, approvals auto-granted, no download cap, no rate
limit, up to 8 subagents — and "still VERIFY every claim with tools before
reporting."

---

## What still protects (unless you opt into ABSOLUTE)

- Destructive-command denies: `rm -rf` / `format c:` / `mkfs` / `shutdown`
  (`DEFAULT_RULES` in `core/guardrails/policy.py`).
- SSRF private-network guard (`check_network_target`).
- Prompt-injection phrase blocking (always-on).

`TITAN_ABSOLUTE_ACCESS=1` lifts the first two. It is an explicit extra opt-in,
never implied by Full Access.

---

## Configuration & runtime toggle

`.env.example`:

```
TITAN_FULL_ACCESS=0
TITAN_ABSOLUTE_ACCESS=0
```

`config.py`:

- `full_access_enabled()` / `absolute_access_enabled()` — read env **at
  call-time** so toggles apply mid-run.
- `set_full_access(on: bool | None)` — module override for runtime use;
  `None` clears the override back to env.

`server.py`:

- `GET /api/config` → includes `"full_access": <bool>`
- `POST /api/config` → accepts `full_access: bool | None` and applies it live.

---

## Verification

- `tests/test_full_access.py` — **32 deterministic tests**, no LLM/network:
  flags + runtime override, step budget, policy access modes, ToolBridge,
  guarded ToolRegistry (approval/deny/sandbox), command timeouts, download
  SSRF/scheme/size, port range, subagent cap, rate limiter, structured clamp,
  API model field.
- Full suite: **288 passed, 1 skipped** (Windows-only screenshot branch).
- `ruff check` clean on every touched file (only the 4 pre-existing `ASYNC221`
  wmctrl warnings remain in the wider tree).