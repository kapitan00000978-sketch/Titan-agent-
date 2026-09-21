# Titan Agent — Phase 6: OmniRoute Provider (Auto-Routing Gateway)

Phase 6 adds **OmniRoute**, a self-hosted AI gateway
(`http://localhost:20128/v1`) that exposes six virtual `auto*` models. Instead of
Titan picking one provider, each request is **routed automatically** to the best
available provider/model behind the gateway — one key, no per-provider fallback
logic in Titan's own config.

The gateway was **verified live** against the real `localhost:20128` dashboard
key before this phase was written: every `auto*` model returned HTTP 200 chat
completions (`auto/offline` intentionally replies empty, since no local provider
is registered).

## 1. The six auto-routing models

| CLI model | Routing intent |
|---|---|
| `auto` | balanced default |
| `auto/coding` | code-first routing |
| `auto/fast` | low-latency routing |
| `auto/smart` | quality-first routing |
| `auto/offline` | local/offline models only |
| `auto/cheap` | cheapest available |

## 2. Config — `titan_agent/config.py` + `config_v2.py`

| Env var | Default | Meaning |
|---|---|---|
| `OMNI_API_KEY` | `""` | gateway key (from the localhost:20128 dashboard) |
| `OMNI_BASE_URL` | `http://localhost:20128/v1` | OpenAI-compatible gateway endpoint |
| `OMNI_MODEL` | `auto` | default routing model |
| `OMNI_AUTO_MODELS` | 6-tuple above | catalog shown in the UI / tests |

- `config.py` — provider precedence chain now includes OmniRoute: **OpenRouter →
  OmniRoute → Kimi K3 → GLM-5.3 Flash → DeepSeek → Groq → OpenAI → Ollama**. With
  `OMNI_API_KEY` set, `TITAN_PROVIDER`/`TITAN_MODEL` default to `omni`/`auto`.
- `config_v2.py` — `LLMSettings` gains `omni_base_url` / `omni_api_key` /
  `omni_model` fields (Pydantic settings layer).

## 3. LLM client — `titan_agent/llm_client.py`

The `omni` provider branch in `_setup_credentials` treats OmniRoute as an
OpenAI-compatible `/v1` gateway. `chat_completion` raises a clear error if the
gateway is not running (instead of a confusing connection error).

## 4. Web UI — `web_ui/index.html` + `app.js`

- OmniRoute added to the provider dropdown and as a launch option.
- Six quick-select **model chips** (`auto`, `auto/coding`, `auto/fast`,
  `auto/smart`, `auto/offline`, `auto/cheap`), each with its own color accent.

## 5. Terminal / headless usage

```bash
python -m titan_agent.headless "Your task here" --provider omni --model auto --json --auto-commit
python -m titan_agent.headless "Summarize the workspace" --provider omni --model auto/coding
```

Without `TITAN_PROVIDER=omni` in `.env`, use `--provider omni` explicitly.
`.env` ships with `TITAN_PROVIDER=omni` / `TITAN_MODEL=auto` as the server-side
default; Puter stays available for the in-browser path.

## 6. Files

| file | change |
|---|---|
| `titan_agent/config.py` | `OMNI_*` constants + precedence chain insert |
| `titan_agent/config_v2.py` | `LLMSettings.omni_*` fields |
| `titan_agent/llm_client.py` | `omni` branch in `_setup_credentials` + no-gateway error |
| `titan_agent/web_ui/index.html` | provider option + 6 model chips |
| `titan_agent/web_ui/app.js` | provider/model wiring |
| `.env` / `.env.example` | OmniRoute block |
| `tests/test_phase6_omni.py` | **new** — 5 tests |
| `CHANGES.md` | Phase 6 section |

## Verified

- `python -m pytest tests -q` → **225 passed** (220 + Phase 6 tests)
- `python -m ruff check titan_agent` → clean except the 4 known intentional
  `ASYNC221` warnings in `tools.py`
- Live proof — headless run over `auto/coding` completed end-to-end through the
  real gateway; all six `auto*` models returned 200 responses.
```