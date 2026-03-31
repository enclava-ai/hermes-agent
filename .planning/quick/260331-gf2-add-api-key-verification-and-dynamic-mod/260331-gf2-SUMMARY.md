---
phase: quick
plan: 260331-gf2
subsystem: dashboard-settings
tags: [api-key, model-selection, htmx, verify]
key-files:
  created:
    - gateway/dashboard/templates/settings/_model_options.html
    - tests/gateway/dashboard/test_verify_key.py
  modified:
    - gateway/dashboard/settings.py
    - gateway/dashboard/__init__.py
    - gateway/dashboard/templates/settings/_llm.html
decisions:
  - Anthropic hardcoded model list avoids non-OpenAI-compatible /v1/models call
  - httpx.AsyncClient used directly (not aiohttp) since hermes already depends on httpx
  - Model options partial renders either select dropdown or error flash with text input fallback
metrics:
  duration_minutes: 3
  completed: "2026-03-31T09:56:20Z"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 7
---

# Quick Task 260331-gf2: Add API Key Verification and Dynamic Model Dropdown

API key verification endpoint with dynamic model dropdown for the LLM settings tab, replacing manual model name entry with a provider-validated select after verification.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Backend verify-key endpoint and model options partial | 708c912b (test), 0e66ddc9 (feat) | settings.py, __init__.py, _model_options.html, test_verify_key.py |
| 2 | Frontend -- Verify button, HTMX swap, model dropdown UX | 1bc9bd3b | _llm.html |

## What Was Built

**POST /settings/llm/verify-key** endpoint that:
- Accepts provider, api_key, api_key_env_var, model_name from form data
- Looks up provider in PROVIDER_REGISTRY; rejects non-api_key auth types gracefully
- Resolves API key: prefers user-entered value, falls back to env var, skips redacted sentinels
- **Anthropic special case**: returns hardcoded model list (claude-opus-4, claude-sonnet-4, claude-sonnet-4-20250514, claude-haiku-3.5, claude-3-5-haiku-20241022) without any HTTP call
- **Other providers**: GETs `{inference_base_url}/models` with Bearer auth, parses OpenAI-format response, sorts alphabetically
- Returns `_model_options.html` partial -- either a `<select>` dropdown or error flash with text input fallback

**Frontend changes** to `_llm.html`:
- Model input wrapped in `#model-input-area` div for HTMX swap target
- "Verify Key & Load Models" button in api-key-section with hx-post, hx-target, hx-include
- Loading spinner indicator during verification
- JavaScript resets model area back to text input when switching to non-api_key provider

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED
