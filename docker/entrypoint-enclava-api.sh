#!/bin/bash
set -euo pipefail

# Enclava CAP v1 mode:
# - persistent Hermes home on the encrypted data volume
# - OpenAI-compatible HTTP API exposed on plain HTTP inside the pod
# - public TLS terminates in the confidential tenant-ingress sidecar

export API_SERVER_ENABLED="${API_SERVER_ENABLED:-true}"
export API_SERVER_HOST="${API_SERVER_HOST:-0.0.0.0}"
export API_SERVER_PORT="${API_SERVER_PORT:-${PORT:-8000}}"

HERMES_HOME="${HERMES_HOME:-/state/data}"
export HERMES_HOME

if [ "$$" = "1" ] && [ -z "${HERMES_ENCLAVA_TINI_WRAPPED:-}" ] && command -v tini >/dev/null 2>&1; then
  export HERMES_ENCLAVA_TINI_WRAPPED=1
  exec /usr/bin/tini -g -- "$0" "$@"
fi

if [ -n "${ENCLAVA_CONTAINER_NAME:-}" ] && [ -z "${HERMES_ENCLAVA_WAIT_EXEC_DONE:-}" ]; then
  export HERMES_ENCLAVA_WAIT_EXEC_DONE=1
  exec /usr/local/bin/enclava-wait-exec "$0" "$@"
fi

: "${HERMES_CAP_CONFIG_DIRS:=/run/enclava/config /state/.enclava/config /data/.enclava/config}"
if [ -z "${HERMES_CAP_CONFIG_WAIT_SECONDS+x}" ]; then
  if [ -n "${ENCLAVA_CONTAINER_NAME:-}" ]; then
    HERMES_CAP_CONFIG_WAIT_SECONDS=300
  else
    HERMES_CAP_CONFIG_WAIT_SECONDS=0
  fi
fi

is_valid_env_key() {
  case "$1" in
    ''|[!A-Za-z_]*|*[!A-Za-z0-9_]*)
      return 1
      ;;
  esac
  return 0
}

first_cap_config_dir() {
  for dir in $HERMES_CAP_CONFIG_DIRS; do
    if [ -d "$dir" ]; then
      printf '%s\n' "$dir"
      return 0
    fi
  done
  return 1
}

cap_config_ready_for_start() {
  if [ -n "${API_SERVER_KEY:-}" ]; then
    return 0
  fi

  case "$API_SERVER_HOST" in
    0.0.0.0|::)
      for dir in $HERMES_CAP_CONFIG_DIRS; do
        if [ -f "$dir/API_SERVER_KEY" ]; then
          return 0
        fi
      done
      return 1
      ;;
  esac

  for dir in $HERMES_CAP_CONFIG_DIRS; do
    if [ -f "$dir/.ready" ]; then
      return 0
    fi
  done
  return 1
}

wait_for_cap_config() {
  seconds="$HERMES_CAP_CONFIG_WAIT_SECONDS"
  case "$seconds" in
    ''|*[!0-9]*)
      echo "HERMES_CAP_CONFIG_WAIT_SECONDS must be an integer" >&2
      exit 1
      ;;
  esac
  [ "$seconds" -gt 0 ] || return 0

  elapsed=0
  while [ "$elapsed" -lt "$seconds" ]; do
    if cap_config_ready_for_start; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done

  echo "CAP config was not ready after ${seconds}s; continuing with current environment" >&2
}

load_cap_config() {
  dir="$(first_cap_config_dir || true)"
  [ -n "${dir:-}" ] || return 0

  for path in "$dir"/*; do
    [ -f "$path" ] || continue
    key="${path##*/}"
    is_valid_env_key "$key" || continue
    value="$(cat "$path")"
    export "$key=$value"
  done
}

wait_for_cap_config
load_cap_config

case "$API_SERVER_HOST" in
  0.0.0.0|::)
    if [ -z "${API_SERVER_KEY:-}" ]; then
      echo "API_SERVER_KEY is required when API_SERVER_HOST=$API_SERVER_HOST" >&2
      exit 64
    fi
    ;;
esac

if [ -n "${HERMES_DASHBOARD:-}" ]; then
  echo "HERMES_DASHBOARD is ignored by the Enclava API-only entrypoint" >&2
fi
unset HERMES_DASHBOARD

# Seed config.yaml with api_server enabled if no config exists yet.
if [ ! -f "$HERMES_HOME/config.yaml" ]; then
  mkdir -p "$HERMES_HOME"
  cp /opt/hermes/docker/enclava-config.yaml "$HERMES_HOME/config.yaml"
  if [ -n "${HERMES_INFERENCE_PROVIDER:-}" ] || [ -n "${HERMES_INFERENCE_MODEL:-}" ]; then
    {
      printf '\nmodel:\n'
      if [ -n "${HERMES_INFERENCE_PROVIDER:-}" ]; then
        printf '  provider: %s\n' "$HERMES_INFERENCE_PROVIDER"
      fi
      if [ -n "${HERMES_INFERENCE_MODEL:-}" ]; then
        printf '  default: %s\n' "$HERMES_INFERENCE_MODEL"
      fi
    } >> "$HERMES_HOME/config.yaml"
  fi
  echo "Seeded config.yaml with Enclava API defaults"
fi

mkdir -p "$HERMES_HOME"/{cron,sessions,logs,hooks,memories,skills,skins,plans,workspace,home}
export HOME="${HOME:-$HERMES_HOME/home}"

if [ ! -f "$HERMES_HOME/.env" ]; then
  cp /opt/hermes/.env.example "$HERMES_HOME/.env"
fi

if [ ! -f "$HERMES_HOME/SOUL.md" ]; then
  cp /opt/hermes/docker/SOUL.md "$HERMES_HOME/SOUL.md"
fi

if [ ! -f "$HERMES_HOME/auth.json" ] && [ -n "${HERMES_AUTH_JSON_BOOTSTRAP:-}" ]; then
  printf '%s' "$HERMES_AUTH_JSON_BOOTSTRAP" > "$HERMES_HOME/auth.json"
  chmod 600 "$HERMES_HOME/auth.json" 2>/dev/null || true
fi

if [ -d /opt/hermes/skills ]; then
  python3 /opt/hermes/tools/skills_sync.py
fi

exec hermes gateway
