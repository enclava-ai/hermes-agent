#!/bin/bash
set -euo pipefail

# Enclava platform mode:
# - persistent Hermes home on the encrypted data volume
# - OpenAI-compatible HTTP API + dashboard exposed on plain HTTP inside the pod
# - public TLS terminates in the confidential tenant-ingress sidecar
# - LLM provider configured through the dashboard by the user

export API_SERVER_ENABLED="${API_SERVER_ENABLED:-true}"
export API_SERVER_HOST="${API_SERVER_HOST:-0.0.0.0}"
export API_SERVER_PORT="${API_SERVER_PORT:-${PORT:-8000}}"

HERMES_HOME="${HERMES_HOME:-/opt/data}"

# Seed config.yaml with api_server enabled if no config exists yet.
# The dashboard (mounted as subapp on the api_server) lets users
# configure LLM provider, platforms, and skills through the browser.
if [ ! -f "$HERMES_HOME/config.yaml" ]; then
  mkdir -p "$HERMES_HOME"
  cp /opt/hermes/docker/enclava-config.yaml "$HERMES_HOME/config.yaml"
  echo "Seeded config.yaml with Enclava defaults (api_server + dashboard)"
fi

exec /opt/hermes/docker/entrypoint.sh gateway
