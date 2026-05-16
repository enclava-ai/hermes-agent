# Hermes On Enclava Platform

This is the supported way to run Hermes on the current Enclava confidential app platform.

It uses:

- Hermes gateway and dashboard in the same tenant container
- built-in gateway HTTP API bound only to `127.0.0.1:18080`
- public Hermes dashboard on the CAP app port
- persistent `HERMES_HOME` on the encrypted app volume
- confidential public TLS terminated by the platform `tenant-ingress` sidecar

Hermes itself serves plain HTTP inside the pod. CAP handles public TLS and the
confidential status and attestation endpoints.

## Generator Integration

Hermes can target the generic tenant scaffold directly.

For the existing shared component in `enclava-tenant-manifests`, use:

```bash
python3 /path/to/hermes-agent/scripts/deploy_enclava_confidential_app.py \
  --tenant flowforge-1 \
  --instance-name hermes-agent \
  --image ghcr.io/your-org/hermes-agent-enclava:latest
```

That wrapper calls `enclava-tenant-manifests/scripts/deploy-confidential-app.py`
with Hermes defaults and reuses the checked-in `components/hermes-agent`
component by default. In reuse mode it also updates the shared component's
pinned workload image, attestation-proxy image, and attestation policy env vars
in `components/hermes-agent/statefulset.yaml` so the deployed workload rolls to
the requested Hermes image.

For a brand-new generated component name, disable reuse:

```bash
python3 /path/to/hermes-agent/scripts/deploy_enclava_confidential_app.py \
  --tenant flowforge-1 \
  --instance-name hermes-agent-canary \
  --app-name hermes-agent-canary \
  --image ghcr.io/your-org/hermes-agent-enclava:latest \
  --no-reuse-component
```

That path injects `deploy/enclava/startup.sh` into the generated startup
ConfigMap, so the default confidential-workload bootstrap still launches Hermes
correctly.

## Runtime Contract

Hermes must run with:

- `HERMES_HOME=/state/data`
- `API_SERVER_ENABLED=true`
- `API_SERVER_HOST=127.0.0.1`
- `API_SERVER_PORT=18080`
- `HERMES_DASHBOARD_HOST=0.0.0.0`
- `HERMES_DASHBOARD_PORT=8000`
- `HERMES_DASHBOARD_AUTH_TOKEN=<required>`

`HERMES_HOME` is respected by the Enclava wrapper entrypoint and the dashboard.
It is no longer only a documentation-level contract.

When running under CAP, the entrypoint waits for confidential CAP config and
exports valid keys from `/state/.enclava/config` before it validates the
dashboard auth token. This lets `enclava deploy --set` and `--set-file` deliver
the token without exposing it in Kubernetes env vars.

The public health endpoint is:

- `GET /health`

The public user surface is the Hermes dashboard. The gateway API remains
available only to local processes in the tenant container at `127.0.0.1:18080`.
The public hostname must continue to expose only the dashboard and the CAP
confidential status and attestation endpoints.

## Dashboard Auth

`HERMES_DASHBOARD_AUTH_TOKEN` is required when the dashboard binds to all
interfaces. Unauthenticated dashboard requests return `401`.

Secret Agent can initiate a session by redirecting the user once with:

```text
?dashboard_token=<short-lived-token>
```

The dashboard accepts that token, serves the SPA, and sets an HTTP-only
`hermes_dashboard_access` cookie for subsequent browser requests. This is a
simple handoff bridge until Secret Agent provides a full OIDC or signed-JWT
dashboard integration.

## Container Entry Point

The repo includes a platform-specific wrapper:

- `/opt/hermes/docker/entrypoint-enclava.sh`
- `deploy/enclava/startup.sh`
- `/usr/local/bin/enclava-wait-exec`

It does five things:

1. waits for `/run/enclava/init-ready` through `enclava-wait-exec` when CAP sets `ENCLAVA_CONTAINER_NAME`
2. loads confidential CAP config before enforcing dashboard auth
3. enables the gateway API on localhost port `18080`
4. starts the dashboard on app port `8000`
5. keeps both processes supervised under `tini`

Then it runs:

```bash
hermes gateway
hermes dashboard --host 0.0.0.0 --port 8000 --no-open --insecure
```

The OpenAI-compatible API server is implemented as a gateway platform adapter,
but it is intentionally not exposed by CAP ingress.

## Required Secrets

At minimum, the deployment needs:

- one LLM provider credential
  - example: `OPENROUTER_API_KEY`
- `HERMES_DASHBOARD_AUTH_TOKEN`

To preseed first-boot model settings, use:

- `HERMES_INFERENCE_PROVIDER`
- `HERMES_INFERENCE_MODEL`

Typical useful additions:

- `EXA_API_KEY`
- `FIRECRAWL_API_KEY`
- `PARALLEL_API_KEY`
- `BROWSERBASE_API_KEY`
- `BROWSERBASE_PROJECT_ID`
- `VOICE_TOOLS_OPENAI_KEY`
- messaging credentials only if you actually enable those platforms

If you publish attestation policy artifacts from the Enclava GitHub workflow,
pass these to the deploy helper so the shared component advertises them through
the attestation sidecar:

- `--attestation-policy-url`
- `--attestation-policy-sha256`
- `--attestation-policy-signature-url`

## Recommended Enclava App Settings

Inside the confidential platform, the Hermes app container should look like this:

- command:
  - `/usr/bin/tini`
  - `-g`
  - `--`
  - `/opt/hermes/docker/entrypoint-enclava.sh`
- app port:
  - `8000`
- health path:
  - `/health`
- persistent mount for Hermes home:
  - `/state/data`

Set `[storage].paths = []` in `enclava.toml`. CAP exposes decrypted state at
`/state`; declaring app-specific storage paths makes CAP render per-app bind
mounts, which are not supported by the current Kata runtime path.

The public hostname should be exposed by the platform sidecar on:

- `https://<app>.<client>.enclava.dev`

## Minimal Environment Example

```env
HERMES_HOME=/state/data
API_SERVER_ENABLED=true
API_SERVER_HOST=127.0.0.1
API_SERVER_PORT=18080
HERMES_DASHBOARD_HOST=0.0.0.0
HERMES_DASHBOARD_PORT=8000
HERMES_DASHBOARD_AUTH_TOKEN=replace-me

OPENROUTER_API_KEY=replace-me
HERMES_INFERENCE_PROVIDER=openrouter
HERMES_INFERENCE_MODEL=anthropic/claude-opus-4.6

EXA_API_KEY=
FIRECRAWL_API_KEY=
PARALLEL_API_KEY=
```

## Important Limits

This prepares Hermes for the current platform shape.

It does not solve:

- full OIDC or SAML sign-in inside Hermes
- tenant-specific RBAC inside Hermes
- automatic generation of Enclava Kustomize manifests
- secret provisioning in the platform repo

Those are deployment-layer tasks, not Hermes runtime tasks.
