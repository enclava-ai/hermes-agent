# Hermes Onboarding Wizard — Dashboard Plugin

Self-contained plugin that adds a "Setup" tab to the Hermes web dashboard for
guided LLM + messaging-platform configuration.

## Why a plugin?

Upstream ships its own dashboard (`hermes_cli/web_server.py` + `web/`).
Implementing the wizard as a plugin instead of patching upstream files means:

- **Zero modifications to upstream files** → trivial future merges from
  `upstream/main`.
- **Plugin contract is documented and stable** → this is the surface upstream
  exposes to third parties; least likely to break.
- **No build tooling** → vanilla JS using `window.__HERMES_PLUGIN_SDK__`.

## Layout

```
dashboard/
├── manifest.json          # tab path, icon, JS entry, API module
├── plugin_api.py          # FastAPI router → /api/plugins/onboarding-wizard/*
├── platform_schema.py     # field definitions per messaging platform
└── dist/index.js          # vanilla-JS IIFE (no bundler)
```

## Stable contract with upstream

The plugin depends on:

| Surface | Where | Risk if upstream changes |
| --- | --- | --- |
| `plugins/<name>/dashboard/manifest.json` discovery | `hermes_cli/web_server.py:_discover_dashboard_plugins` | Low — upstream sells this to third parties |
| `/api/plugins/<name>/*` routing | same file | Low — same |
| `window.__HERMES_PLUGIN_SDK__` (React, hooks, components, fetchJSON) | `web/src/plugins/PluginPage.tsx` | Medium — version-checked at load time |
| `window.__HERMES_PLUGINS__.register(name, Component)` | same file | Medium — version-checked |
| `hermes_cli.config.{load_config,save_config,save_env_value,get_env_value,redact_key,is_managed}` | `hermes_cli/config.py` | Low — internal but very widely used |
| `hermes_cli.auth.PROVIDER_REGISTRY` | `hermes_cli/auth.py` | Low — same |
| `gateway.config.Platform` enum | `gateway/config.py` | Low — same |

`dist/index.js` reads `SDK.version` at load. If the major bumps, a yellow
warning banner appears at the top of the wizard (instead of silently
breaking).

## API endpoints

All under `/api/plugins/onboarding-wizard/`:

- `GET /state` — wizard draft + initial render context for all steps
- `POST /llm` — save Step 1 (provider + model + key)
- `POST /test` — test platform connection
- `POST /complete` — apply config + env atomically
- `POST /reset` — clear draft

Auth: upstream's `auth_middleware` deliberately bypasses `/api/plugins/*`, so
the plugin currently inherits whatever transport-level protection the host
provides (loopback bind by default; Caddy basic_auth in front; or our own
`auth_proxy` companion).

## Adding a new platform

1. Add an entry to `platform_schema.py` with field definitions.
2. (Optional) Add a `_test_<platform>(form_data)` function in `plugin_api.py`
   and register it in `_TEST_HANDLERS`.

## Maintenance checklist when merging upstream

After `git merge upstream/main`:

- [ ] Confirm `_discover_dashboard_plugins` still scans `plugins/*/dashboard/manifest.json`.
- [ ] Confirm `_PUBLIC_API_PATHS`/`auth_middleware` still bypass `/api/plugins/*`.
- [ ] Confirm `window.__HERMES_PLUGIN_SDK__.version` major hasn't bumped (or update `SDK_MAJOR_TESTED` after audit).
- [ ] Confirm `PROVIDER_REGISTRY` and `gateway.config.Platform` still exist.

If any of those fail, the plugin will surface the problem at import time or
on first page load — no silent breakage.
