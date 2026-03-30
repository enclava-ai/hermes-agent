#!/bin/bash
set -euo pipefail

# Enclava platform mode:
# - persistent Hermes home on the encrypted data volume
# - OpenAI-compatible HTTP API exposed on plain HTTP inside the pod
# - public TLS terminates in the confidential tenant-ingress sidecar

export API_SERVER_ENABLED="${API_SERVER_ENABLED:-true}"
export API_SERVER_HOST="${API_SERVER_HOST:-0.0.0.0}"
export API_SERVER_PORT="${API_SERVER_PORT:-${PORT:-8000}}"

if [ "${API_SERVER_HOST}" = "0.0.0.0" ] && [ -z "${API_SERVER_KEY:-}" ]; then
  echo "API_SERVER_KEY is required when binding Hermes API server to 0.0.0.0" >&2
  exit 1
fi

exec /opt/hermes/docker/entrypoint.sh gateway
