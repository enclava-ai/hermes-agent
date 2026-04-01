# Hermes On Enclava Platform

This is the supported way to run Hermes on the current Enclava confidential app platform.

It uses:

- Hermes gateway in foreground
- built-in OpenAI-compatible API server
- persistent `HERMES_HOME` on the encrypted app volume
- confidential public TLS terminated by the platform `tenant-ingress` sidecar

Hermes itself serves plain HTTP inside the pod.

## Generator Integration

Hermes can now target the generic tenant scaffold directly.

For the existing shared component in `enclava-tenant-manifests`, use:

```bash
python3 /path/to/hermes-agent/scripts/deploy_enclava_confidential_app.py \
  --tenant flowforge-1 \
  --instance-name hermes-agent \
  --image ghcr.io/your-org/hermes-agent-enclava:latest
```

That wrapper calls `enclava-tenant-manifests/scripts/deploy-confidential-app.py` with Hermes defaults and reuses the checked-in `components/hermes-agent` component by default.

For a brand-new generated component name, disable reuse:

```bash
python3 /path/to/hermes-agent/scripts/deploy_enclava_confidential_app.py \
  --tenant flowforge-1 \
  --instance-name hermes-agent-canary \
  --app-name hermes-agent-canary \
  --image ghcr.io/your-org/hermes-agent-enclava:latest \
  --no-reuse-component
```

That path injects `deploy/enclava/startup.sh` into the generated startup ConfigMap, so the default confidential-workload bootstrap still launches Hermes correctly.

## Runtime Contract

Hermes must run with:

- `API_SERVER_ENABLED=true`
- `API_SERVER_HOST=0.0.0.0`
- `API_SERVER_PORT=8000`
- `API_SERVER_KEY=<required>`
- `HERMES_HOME=/opt/data`

The health endpoint is:

- `GET /health`

The main API root is:

- `POST /v1/chat/completions`
- `POST /v1/responses`

## Container Entry Point

The repo now includes a platform-specific wrapper:

- `/opt/hermes/docker/entrypoint-enclava-api.sh`
- `deploy/enclava/startup.sh`

It does three things:

1. enables the API server
2. binds it to `0.0.0.0`
3. defaults the port to `${PORT:-8000}`

Then it runs:

```bash
hermes gateway
```

This is intentional. The API server is implemented as a gateway platform adapter.

## Required Secrets

At minimum, the deployment needs:

- one LLM provider credential
  - example: `OPENROUTER_API_KEY`
- `API_SERVER_KEY`

Typical useful additions:

- `EXA_API_KEY`
- `FIRECRAWL_API_KEY`
- `PARALLEL_API_KEY`
- `BROWSERBASE_API_KEY`
- `BROWSERBASE_PROJECT_ID`
- `VOICE_TOOLS_OPENAI_KEY`
- messaging credentials only if you actually enable those platforms

## Recommended Enclava App Settings

Inside the confidential platform, the Hermes app container should look like this:

- command:
  - `/opt/hermes/docker/entrypoint-enclava-api.sh`
- app port:
  - `8000`
- health path:
  - `/health`
- persistent mount for Hermes home:
  - `/opt/data`

The public hostname should be exposed by the platform sidecar on:

- `https://<app>.<client>.enclava.dev`

## Minimal Environment Example

```env
HERMES_HOME=/opt/data
API_SERVER_ENABLED=true
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=8000
API_SERVER_KEY=replace-me

OPENROUTER_API_KEY=replace-me
LLM_MODEL=anthropic/claude-opus-4.6

EXA_API_KEY=
FIRECRAWL_API_KEY=
PARALLEL_API_KEY=
```

## Important Limits

This prepares Hermes for the current platform shape.

It does not solve:

- multi-user auth in front of Hermes
- tenant-specific RBAC inside Hermes
- automatic generation of Enclava Kustomize manifests
- secret provisioning in the platform repo

Those are deployment-layer tasks, not Hermes runtime tasks.
