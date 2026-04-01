#!/bin/sh
set -eu

# Generated confidential-workload components can keep their default
# bootstrap command and hand off to this repo-owned startup hook.
export HERMES_HOME="${HERMES_HOME:-/opt/data}"

exec /opt/hermes/docker/entrypoint-enclava-api.sh
