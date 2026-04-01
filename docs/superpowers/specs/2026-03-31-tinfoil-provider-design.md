# Tinfoil Provider Integration

**Date:** 2026-03-31
**Status:** Approved

## Overview

Add Tinfoil as a first-class LLM provider in hermes-agent using the `tinfoil-python` client library.

Tinfoil is OpenAI-compatible at the payload level, but this integration intentionally does **not** treat it as "just another chat-completions endpoint." We keep a dedicated `api_mode: "tinfoil"` so Hermes has a clear, auditable boundary for requests that must remain in confidential mode.

## Design Goals

1. **Fail closed for confidentiality.** If the active provider is Tinfoil, Hermes must not silently route any inference request through OpenAI, OpenRouter, Anthropic, or a generic custom endpoint.
2. **Minimize code churn.** Reuse the existing `chat_completions` request/response shapes wherever possible. The dedicated api mode exists for routing assurance, not because Tinfoil needs a different prompt format.
3. **Keep the change set upstreamable.** Prefer a small number of targeted branches over large refactors.

## Architecture

A new `api_mode: "tinfoil"` is introduced, but it is a **routing/security mode**, not a new prompt schema.

- Hermes continues to build standard chat-completions-style payloads.
- Tinfoil execution happens only through `TinfoilAI`, never through the generic `OpenAI` client.
- Any helper path that cannot stay inside Tinfoil should fail with a clear error instead of falling back to another provider.

This keeps the diff small while making the confidentiality guarantee explicit in code review.

## Minimal Change Set

Nine files change or are created:

| File | Change |
|---|---|
| `hermes_cli/auth.py` | Add `"tinfoil"` to `PROVIDER_REGISTRY` |
| `hermes_cli/runtime_provider.py` | Add `api_mode: "tinfoil"` resolution branch |
| `agent/tinfoil_adapter.py` | New — Tinfoil client init + thin execution helpers |
| `run_agent.py` | Add Tinfoil initialization and execution branches; fail closed on rebuild/fallback paths |
| `agent/auxiliary_client.py` | Add explicit Tinfoil routing; disable non-confidential fallback when Tinfoil is active |
| `hermes_cli/models.py` | Add provider labels/catalog lookup for Tinfoil |
| `hermes_cli/setup.py` | Let setup/model selection fetch Tinfoil models with the Tinfoil client |
| `pyproject.toml` | Add `tinfoil` dependency |
| `cli-config.yaml.example` | Document the new provider |

## Components & Data Flow

### Provider Registration (`hermes_cli/auth.py`)

Add to `PROVIDER_REGISTRY`:

```python
ProviderConfig(
    id="tinfoil",
    name="Tinfoil (Confidential AI)",
    auth_type="api_key",
    inference_base_url="https://inference.tinfoil.sh",
    api_key_env_vars=("TINFOIL_API_KEY", "TINFOIL_TOKEN"),
)
```

Notes:

- We keep `inference_base_url` populated even though the SDK handles enclave/router verification internally.
- This avoids broad breakage in status/setup/model plumbing that assumes API-key providers have a base URL.
- The runtime path still uses `TinfoilAI(api_key=...)`, not a generic OpenAI client pointed at that URL.

### Runtime Resolution (`hermes_cli/runtime_provider.py`)

Add a dedicated branch that resolves:

```python
{
    "provider": "tinfoil",
    "api_mode": "tinfoil",
    "api_key": "<from env>",
    "base_url": "https://inference.tinfoil.sh",
    "source": "env",
}
```

This branch exists so later code can enforce the invariant:

> if `api_mode == "tinfoil"`, all inference calls must stay on the Tinfoil client path.

`_VALID_API_MODES` must be extended to include `"tinfoil"`.

### Adapter (`agent/tinfoil_adapter.py`)

This module should stay deliberately thin.

Responsibilities:

1. **`build_client(api_key) -> TinfoilAI`**  
   Instantiate `TinfoilAI(api_key=api_key)`. Use the SDK defaults so router selection, attestation, certificate pinning, and EHBP remain owned by the Tinfoil library.

2. **`create_chat_completion(client, **kwargs)`**  
   Execute a non-streaming chat completion using the already-built Hermes request payload.

3. **`stream_chat_completion(client, **kwargs)`**  
   Execute a streaming completion and yield chunks in the same shape Hermes already expects from chat-completions streams.

4. **`list_models(api_key) -> list[str]`**  
   Fetch available model IDs through the Tinfoil client, for setup/model selection flows.

Non-goals for this adapter:

- No custom prompt format
- No parallel alternative request builder
- No OpenAI-client emulation beyond what Hermes actually needs

### Agent Loop (`run_agent.py`)

Retain the dedicated api mode, but keep the implementation minimal:

1. **Initialization**
   - If `api_mode == "tinfoil"`, build and store a Tinfoil client via `agent.tinfoil_adapter.build_client(api_key)`.
   - Do not instantiate the generic `OpenAI` client for this mode.
   - Keep `self.base_url` set to the resolved Tinfoil router URL for logging and feature checks, but do not use it to construct the actual client.

2. **Request building**
   - Reuse the existing chat-completions request preparation path.
   - Do **not** add a separate Tinfoil message formatter unless a concrete incompatibility is discovered.

3. **Execution**
   - Where Hermes currently dispatches between `chat_completions`, `codex_responses`, and `anthropic_messages`, add a fourth `tinfoil` branch that delegates to the adapter.
   - This includes both non-streaming and streaming paths.

4. **Fail-closed fallback/rebuild behavior**
   - Any client rebuild, retry, or fallback logic must preserve `api_mode == "tinfoil"` and re-create the Tinfoil client.
   - No silent fallback to OpenRouter or other providers when Tinfoil credentials are missing or a Tinfoil call fails.

### Auxiliary Client (`agent/auxiliary_client.py`)

For minimal and safe integration:

- Add explicit support for `provider="tinfoil"` / `provider="main"` when the main provider is Tinfoil.
- Do **not** insert Tinfoil into the generic `"auto"` fallback chain for unrelated users.
- When the active/main provider is Tinfoil, auxiliary tasks must either:
  - use Tinfoil too, or
  - fail clearly if that task is not yet supported through Tinfoil.

This is the key assurance rule:

> Tinfoil mode may reduce functionality before it is allowed to reduce confidentiality.

Concretely:

- Text-side auxiliary tasks such as compression and web extraction should route through the Tinfoil client when the selected provider is Tinfoil.
- Vision should only be enabled if validated with a known Tinfoil multimodal model; otherwise return a clear unsupported error instead of falling back to OpenRouter/Codex/Anthropic.

### Model Catalog (`hermes_cli/models.py` and `hermes_cli/setup.py`)

To keep the diff small:

- Add Tinfoil provider label/normalization entries.
- Add a `provider_model_ids("tinfoil")` path that uses `agent.tinfoil_adapter.list_models(...)`.
- Teach setup/model selection to use that path for Tinfoil rather than probing the provider with the generic `fetch_api_models()` helper.

This avoids treating Tinfoil as a plain OpenAI-compatible HTTP endpoint in setup flows.

Caching:

- No bespoke cache layer is required for the first version.
- Reuse existing provider-model lookup patterns unless profiling later shows model listing is too expensive.

## Error Handling

| Scenario | Behavior |
|---|---|
| `TINFOIL_API_KEY` not set | Fail at resolution time with a clear provider-specific message |
| Tinfoil SDK missing | Fail at client-build time with install guidance |
| Enclave/router attestation failure | Surface as a descriptive Tinfoil error; do not retry via another provider |
| Auxiliary task would leave Tinfoil | Fail with a message that the task is not yet supported confidentially |
| Model list fetch fails in setup | Warn and allow manual model entry |

## Testing

All tests mock `TinfoilAI` and verify fail-closed behavior. No live enclave calls.

- **`tests/test_tinfoil_provider.py`**
  - registry entry exists
  - runtime resolution returns `api_mode == "tinfoil"`
  - missing API key raises the expected error

- **`tests/test_tinfoil_adapter.py`**
  - client construction
  - non-streaming call path
  - streaming chunk handling
  - model listing

- **`tests/test_run_agent_tinfoil.py`**
  - Tinfoil mode does not instantiate generic `OpenAI`
  - streaming and non-streaming execution stay on the adapter path
  - retry/rebuild paths preserve Tinfoil mode
  - failures do not fall back to OpenRouter/custom

- **`tests/agent/test_auxiliary_client_tinfoil.py`**
  - explicit `provider="tinfoil"` resolves to Tinfoil
  - `main` routes to Tinfoil when the configured provider is Tinfoil
  - unsupported auxiliary tasks fail instead of falling through

- **`tests/test_setup_model_selection.py`** or a new targeted test
  - Tinfoil model selection uses the Tinfoil listing path
  - model-list failure still allows manual model entry

## Out of Scope

- models.dev provider mapping and context-window metadata integration
- Tinfoil-specific prompt caching or reasoning extensions
- Broad status-page polish beyond basic provider/config visibility
- Custom attestation repo overrides or enclave pin overrides in Hermes config
- Automatically enabling Tinfoil as a global auxiliary/vision auto fallback for non-Tinfoil users

## Implementation Note

If this upstreams cleanly, the strongest argument will be:

> the patch adds one provider, one security-oriented api mode, and one thin adapter, while reusing Hermes' existing chat-completions payload shape everywhere else.

That keeps the review focused on confidentiality guarantees instead of transport churn.
