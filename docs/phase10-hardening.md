# Titan Agent — Phase 10: HARNESS HARDENING

Phase 10 does not add new models or new tools. It removes three ways a run
could silently degrade or die, so Titan keeps working on exactly the tasks it
is already good at — only for longer, and through failures that previously
killed it.

The three weaknesses, all in the classic `run_task` loop:

1. **Unbounded context growth.** Every step appends an assistant message and
   its tool results to `messages`, and the whole list is re-sent each
   iteration. With 25–48+ steps (or unbounded FULL ACCESS runs) of large tool
   output, the payload eventually exceeds the provider window and the LLM
   call fails — taking the entire run down with it.
2. **Silently corrupted tool calls.** When the model's arguments JSON failed
   to parse, the harness ran the tool with `{}` — an empty-argument call.
   Best case the model saw a confusing error; worst case a destructive tool
   ran with no inputs while the intended payload was dropped.
3. **Zero LLM-call resilience.** `aiohttp.ClientError`, `OSError` or a
   context-length error at any step meant an immediate error event and a dead
   run. No retry, no recovery.

---

## 1. Context budget trimming — `trim_messages_for_context()`

Pure function (in `titan_agent/agent.py`), called **proactively at the top of
every loop iteration** — a no-op until the living context actually exceeds the
budget, then it trims without corrupting the conversation shape:

- **Head is sacred.** System messages and the first user task message are
  never dropped. Deep runs stay anchored to the original request even after a
  40-step marathon.
- **Newest wins.** The active working window (the most recent steps) is kept
  first — that is the state the model is reasoning about right now.
- **Atomic tool blocks.** An assistant message with `tool_calls` and its
  following `tool` messages are trimmed only together. The resulting message
  array always satisfies the OpenAI-compatible assistant→tool pairing rule,
  so the retried call is never rejected for message-shape reasons.
- **Visible marker.** If anything was dropped, a one-line system message is
  inserted right after the head so the model knows earlier context was
  truncated rather than silently missing.

Configured with **`TITAN_CONTEXT_BUDGET_CHARS`** (default 200 000 chars;
~4 chars ≈ 1 token).

## 2. Tool-call argument repair — `parse_tool_arguments()`

Best-effort repair of the model's arguments payload before it reaches a tool:

| Input | Result |
|---|---|
| `{}` / empty / `None` | `{}` |
| dict (native tool_calls) | pass-through |
| valid JSON | parsed dict |
| ` ```json {…} ``` ` / `` `{…}` `` | fences/backticks stripped, parsed |
| `garbage {…} tail` | the one balanced `{…}` region is extracted |
| `"hello"` / `[1,2]` (non-dict JSON) | wrapped as `{"value": …}` |
| genuinely unparsable | `None` |

On `None` the call is **skipped — never executed with empty args** — and the
raw payload (truncated) is returned as the tool result, so the model sees
exactly what it sent and can resend a valid call. Every `tool_call_id` still
receives exactly one follow-up `tool` message, so the next model request is
structurally valid. This is the Phase 9 tool-policy philosophy applied at the
data level: a broken payload is surfaced, never silently laundered into a
tool call.

## 3. LLM call recovery — `_chat_with_recovery()`

Wraps every loop-iteration model call:

- **Transient errors** (`aiohttp.ClientError`, `OSError`, timeouts) retry with
  linear backoff, bounded by **`TITAN_LLM_TRANSIENT_RETRIES`** (default 2).
  One network hiccup no longer costs an entire deep run.
- **Context-length errors** don't fail fast. The harness doesn't know the
  provider's real window, so it **progressively halves** the payload (current
  size ÷ 2, bounded to ≤ 6 shrinks) and retries. If the provider accepted the
  conversation 5 steps ago, halving lands under its limit again — the run
  degrades to a shorter window instead of dying.
- **API-level failures** (401/403/…) and context errors that trimming cannot
  fix still fail fast, keeping the error contract honest.

---

## Verification

- `tests/test_hardening.py` — **12 deterministic tests**:
  - trim: no-op under budget, head+tail survival, tool-block atomicity, no
    orphan tool messages;
  - parse: valid / wrapped / non-dict / invalid payloads;
  - emit: unparsable call skipped with feedback, valid+bad mixed call order,
    assistant→tool pairing intact;
  - recovery: transient retry recovers, all-retries-exhausted still fails
    cleanly, halving recovers from repeated overflow (unit + end-to-end
    through `run_task`).
- Full suite: **329 passed, 1 skipped**; `ruff check` clean on all touched
  files.