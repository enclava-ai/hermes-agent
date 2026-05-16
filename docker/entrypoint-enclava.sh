#!/bin/bash
set -euo pipefail

# Enclava CAP dashboard mode:
# - persistent Hermes home on the encrypted data volume
# - Hermes gateway and OpenAI-compatible API stay internal on localhost
# - Hermes dashboard is the public app surface behind CAP confidential ingress

export API_SERVER_ENABLED="${API_SERVER_ENABLED:-true}"
export API_SERVER_HOST="${API_SERVER_HOST:-127.0.0.1}"
export API_SERVER_PORT="${API_SERVER_PORT:-18080}"
export HERMES_DASHBOARD_HOST="${HERMES_DASHBOARD_HOST:-0.0.0.0}"
export HERMES_DASHBOARD_PORT="${HERMES_DASHBOARD_PORT:-${PORT:-8000}}"
export GATEWAY_HEALTH_URL="${GATEWAY_HEALTH_URL:-http://127.0.0.1:${API_SERVER_PORT}}"
export HERMES_GATEWAY_RESTART_EXIT_CODES="${HERMES_GATEWAY_RESTART_EXIT_CODES:-all}"
export HERMES_GATEWAY_RESTART_DELAY_SECONDS="${HERMES_GATEWAY_RESTART_DELAY_SECONDS:-1}"

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
  if [ -n "${HERMES_DASHBOARD_AUTH_TOKEN:-}" ] || [ -n "${HERMES_DASHBOARD_ACCESS_TOKEN:-}" ]; then
    return 0
  fi

  for dir in $HERMES_CAP_CONFIG_DIRS; do
    if [ -f "$dir/HERMES_DASHBOARD_AUTH_TOKEN" ] || [ -f "$dir/HERMES_DASHBOARD_ACCESS_TOKEN" ]; then
      return 0
    fi
  done

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

dashboard_auth_token="${HERMES_DASHBOARD_AUTH_TOKEN:-${HERMES_DASHBOARD_ACCESS_TOKEN:-}}"
case "$HERMES_DASHBOARD_HOST" in
  0.0.0.0|::)
    if [ -z "$dashboard_auth_token" ]; then
      echo "dashboard auth token is required when HERMES_DASHBOARD_HOST=$HERMES_DASHBOARD_HOST" >&2
      exit 64
    fi
    ;;
esac

# Seed config.yaml with dashboard-public, API-internal Enclava defaults.
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
  echo "Seeded config.yaml with Enclava dashboard defaults"
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

is_gateway_restart_status() {
  status="$1"
  if [ "$HERMES_GATEWAY_RESTART_EXIT_CODES" = "all" ]; then
    return 0
  fi
  for restart_status in $HERMES_GATEWAY_RESTART_EXIT_CODES; do
    if [ "$status" = "$restart_status" ]; then
      return 0
    fi
  done
  return 1
}

run_gateway_supervisor() {
  trap 'if [ -n "${gateway_pid:-}" ] && kill -0 "$gateway_pid" >/dev/null 2>&1; then kill "$gateway_pid" >/dev/null 2>&1 || true; fi; exit 143' INT TERM

  while true; do
    hermes gateway &
    gateway_pid="$!"

    set +e
    wait "$gateway_pid"
    status="$?"
    set -e
    gateway_pid=""

    if is_gateway_restart_status "$status"; then
      echo "Hermes gateway requested restart with exit code ${status}; restarting gateway inside container"
      sleep "$HERMES_GATEWAY_RESTART_DELAY_SECONDS"
      continue
    fi

    return "$status"
  done
}

shutdown() {
  status="${1:-0}"
  if [ -n "${gateway_supervisor_pid:-}" ] && kill -0 "$gateway_supervisor_pid" >/dev/null 2>&1; then
    kill "$gateway_supervisor_pid" >/dev/null 2>&1 || true
  fi
  if [ -n "${dashboard_pid:-}" ] && kill -0 "$dashboard_pid" >/dev/null 2>&1; then
    kill "$dashboard_pid" >/dev/null 2>&1 || true
  fi
  wait "${gateway_supervisor_pid:-}" "${dashboard_pid:-}" >/dev/null 2>&1 || true
  exit "$status"
}

trap 'shutdown 143' INT TERM

run_gateway_supervisor &
gateway_supervisor_pid="$!"

hermes dashboard \
  --host "$HERMES_DASHBOARD_HOST" \
  --port "$HERMES_DASHBOARD_PORT" \
  --no-open \
  --insecure &
dashboard_pid="$!"

while true; do
  if ! kill -0 "$dashboard_pid" >/dev/null 2>&1; then
    set +e
    wait "$dashboard_pid"
    status="$?"
    set -e
    shutdown "$status"
  fi

  if ! kill -0 "$gateway_supervisor_pid" >/dev/null 2>&1; then
    set +e
    wait "$gateway_supervisor_pid"
    status="$?"
    set -e
    shutdown "$status"
  fi

  sleep 1
done
