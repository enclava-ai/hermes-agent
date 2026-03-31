# Tinfoil Provider Integration

**Date:** 2026-03-31
**Status:** Approved

## Overview

Add Tinfoil as a first-class LLM provider in hermes-agent. Tinfoil provides secure AI model inference through confidential computing infrastructure — requests are routed through cryptographically verified enclaves with TLS certificate pinning and enclave attestation, using the `tinfoil-python` client library.

## Architecture

A new `api_mode: "tinfoil"` is introduced, parallel to the existing `"anthropic_messages"` mode. This keeps all tinfoil-specific logic in a single adapter and makes the protocol boundary explicit.

Six files change or are created:

| File | Change |
|---|---|
| `hermes_cli/auth.py` | Add `"tinfoil"` entry to `PROVIDER_REGISTRY` |
| `hermes_cli/runtime_provider.py` | Add resolution branch returning `api_mode: "tinfoil"` |
| `agent/tinfoil_adapter.py` | New — client init, request building, response parsing, streaming, model catalog fetch |
| `hermes_cli/models.py` | Add tinfoil to provider menu + model catalog fetch/cache logic |
| `run_agent.py` | Add `elif api_mode == "tinfoil"` branch delegating to the adapter |
| `agent/auxiliary_client.py` | Add tinfoil to the side-task fallback chain |

## Components & Data Flow

### Provider Registration (`hermes_cli/auth.py`)

Add to `PROVIDER_REGISTRY`:

```python
ProviderConfig(
    id="tinfoil",
    name="Tinfoil (Confidential AI)",
    auth_type="api_key",
    api_key_env_vars=("TINFOIL_API_KEY", "TINFOIL_TOKEN"),
)
```

No `inference_base_url` — the `TinfoilAI` client auto-selects and verifies a router enclave.

### Runtime Resolution (`hermes_cli/runtime_provider.py`)

New branch resolves:

```python
{
    "provider": "tinfoil",
    "api_mode": "tinfoil",
    "api_key": "<from env>",
    "base_url": None,   # TinfoilAI handles enclave selection internally
    "source": "env",
}
```

`base_url` is explicitly `None` — enclave routing is handled by the `TinfoilAI` client itself as part of its attestation flow.

### Adapter (`agent/tinfoil_adapter.py`)

Four responsibilities:

1. **`build_client(api_key) -> TinfoilAI`** — instantiates `TinfoilAI(api_key=api_key)` with repo-based enclave verification (default). Enclave router is auto-fetched from `https://atc.tinfoil.sh/routers` and attested via GitHub + Sigstore.

2. **`build_request(messages, model, tools, ...) -> dict`** — standard OpenAI chat completions format. Can share helpers with the existing `chat_completions` path.

3. **`parse_response(response)`** and **`stream_response(stream)`** — normalize to hermes internal format (same shape as `chat_completions` responses).

4. **`fetch_model_catalog(client) -> list[str]`** — calls `client.models.list()`, returns model IDs.

### Model Catalog (`hermes_cli/models.py`)

- When provider is `"tinfoil"`: call `fetch_model_catalog()` and cache under a `"tinfoil_catalog"` key in `~/.hermes/model_cache.json` alongside the existing context-length cache.
- Cache entry shape: `{"models": [...], "fetched_at": <unix timestamp>}`
- **TTL:** 24 hours. On cache hit within TTL: use cached list. On miss or expiry: re-fetch from API.
- On fetch failure with stale cache: log warning, use stale data, continue.
- On fetch failure with no cache: raise with a message instructing the user to specify a model explicitly via `--model`.

### Agent Loop (`run_agent.py`)

```python
elif api_mode == "tinfoil":
    from agent.tinfoil_adapter import build_client
    llm_client = build_client(api_key)
```

All subsequent request/response calls use the same `chat_completions`-style interface since `TinfoilAI` is a drop-in `OpenAI` subclass.

### Auxiliary Client (`agent/auxiliary_client.py`)

Add tinfoil to the side-task fallback chain (context compression, web extraction, vision) after the main provider check, before the OpenRouter fallback.

## Error Handling

| Scenario | Behavior |
|---|---|
| `TINFOIL_API_KEY` not set | Fail at resolution time with a clear message (same pattern as other providers) |
| Enclave attestation failure | Surface as a descriptive error pointing to Tinfoil docs, not a generic HTTP error |
| Model catalog fetch fails, no cache | Raise with instructions to specify `--model` explicitly |
| Model catalog fetch fails, stale cache | Log warning, use stale data, continue |

## Testing

All tests mock the `TinfoilAI` client — no live enclave calls.

- **`tests/test_tinfoil_provider.py`**: resolution returns correct dict, missing API key error, `api_mode` is `"tinfoil"`
- **`tests/test_tinfoil_adapter.py`**: request format matches OpenAI spec, response parsing, streaming chunk handling
- **`tests/test_tinfoil_model_catalog.py`**: cache hit path, cache miss triggers fetch, stale cache fallback on fetch failure

## Out of Scope

- Measurement-based (direct SNP) verification — repo-based default covers the primary use case
- Per-enclave URL override via config — can be added later if needed
- Custom `repo` override for attestation — not exposed at the hermes config level
