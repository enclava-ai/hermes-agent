from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_enclava_dockerfile_installs_existing_extras():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    extras = pyproject["project"]["optional-dependencies"]
    dockerfile = (ROOT / "Dockerfile.enclava").read_text()

    assert ".[homeassistant,web]" in dockerfile
    assert ".[web" not in dockerfile
    assert "homeassistant" in extras
    assert "web" in extras


def test_enclava_dockerfile_builds_dashboard_assets():
    dockerfile = (ROOT / "Dockerfile.enclava").read_text()

    assert "FROM node:22" in dockerfile
    assert "npm" in dockerfile
    assert "cd web" in dockerfile
    assert "npm run build" in dockerfile
    assert "HERMES_WEB_DIST=/opt/hermes/hermes_cli/web_dist" in dockerfile


def test_enclava_dockerfile_provides_wait_exec_helper():
    dockerfile = (ROOT / "Dockerfile.enclava").read_text()

    assert "docker/enclava-wait-exec" in dockerfile
    assert "/usr/local/bin/enclava-wait-exec" in dockerfile


def test_enclava_dockerfile_uses_pid1_init():
    dockerfile = (ROOT / "Dockerfile.enclava").read_text()

    assert "tini" in dockerfile
    assert (
        'ENTRYPOINT ["/usr/bin/tini", "-g", "--", '
        '"/opt/hermes/docker/entrypoint-enclava.sh"]'
    ) in dockerfile


def test_enclava_descriptor_uses_pid1_init_command():
    descriptor = tomllib.loads((ROOT / "enclava.toml").read_text())

    assert descriptor["app"]["command"] == [
        "/usr/bin/tini",
        "-g",
        "--",
        "/opt/hermes/docker/entrypoint-enclava.sh",
    ]


def test_enclava_package_uses_state_directly_without_app_bind_mounts():
    descriptor = tomllib.loads((ROOT / "enclava.toml").read_text())
    dockerfile = (ROOT / "Dockerfile.enclava").read_text()
    entrypoint = (ROOT / "docker/entrypoint-enclava.sh").read_text()
    docs = (ROOT / "docs/ENCLAVA_PLATFORM.md").read_text()
    workflow = (ROOT / ".github/workflows/enclava-build.yml").read_text()

    assert descriptor["storage"]["paths"] == []
    assert "HERMES_HOME=/state/data" in dockerfile
    assert "HERMES_HOME=\"${HERMES_HOME:-/state/data}\"" in entrypoint
    assert "/opt/data" not in dockerfile
    assert "/opt/data" not in entrypoint
    assert "/opt/data" not in docs
    assert "HERMES_HOME=/opt/data" not in workflow


def test_enclava_entrypoint_waits_under_cap_only_once():
    entrypoint = (ROOT / "docker/entrypoint-enclava.sh").read_text()

    assert "ENCLAVA_CONTAINER_NAME" in entrypoint
    assert "HERMES_ENCLAVA_WAIT_EXEC_DONE" in entrypoint
    assert 'exec /usr/local/bin/enclava-wait-exec "$0" "$@"' in entrypoint


def test_enclava_entrypoint_keeps_api_server_internal():
    entrypoint = (ROOT / "docker/entrypoint-enclava.sh").read_text()

    assert "API_SERVER_HOST" in entrypoint
    assert "127.0.0.1" in entrypoint
    assert "API_SERVER_PORT" in entrypoint
    assert "18080" in entrypoint
    assert 'API_SERVER_HOST="${API_SERVER_HOST:-127.0.0.1}"' in entrypoint
    assert "API_SERVER_KEY is required" not in entrypoint


def test_enclava_entrypoint_requires_dashboard_auth_for_public_bind():
    entrypoint = (ROOT / "docker/entrypoint-enclava.sh").read_text()

    assert "HERMES_DASHBOARD_AUTH_TOKEN" in entrypoint
    assert "HERMES_DASHBOARD_ACCESS_TOKEN" in entrypoint
    assert "dashboard auth token is required" in entrypoint


def test_enclava_entrypoint_loads_cap_config_before_api_key_guard():
    entrypoint = (ROOT / "docker/entrypoint-enclava.sh").read_text()
    docs = (ROOT / "docs/ENCLAVA_PLATFORM.md").read_text()

    assert "HERMES_CAP_CONFIG_DIRS" in entrypoint
    assert "/state/.enclava/config" in entrypoint
    assert "wait_for_cap_config" in entrypoint
    assert "load_cap_config" in entrypoint
    auth_guard = entrypoint.index("dashboard auth token is required")
    assert entrypoint.index("wait_for_cap_config") < auth_guard
    assert entrypoint.index("load_cap_config") < auth_guard
    assert "CAP config" in docs


def test_enclava_entrypoint_does_not_delegate_to_standard_docker_entrypoint():
    entrypoint = (ROOT / "docker/entrypoint-enclava.sh").read_text()

    assert "/opt/hermes/docker/entrypoint.sh" not in entrypoint
    assert "hermes gateway" in entrypoint
    assert "hermes dashboard" in entrypoint


def test_enclava_entrypoint_supervises_gateway_restart_without_exiting_container():
    entrypoint = (ROOT / "docker/entrypoint-enclava.sh").read_text()

    assert "GATEWAY_SERVICE_RESTART_EXIT_CODE" in (ROOT / "gateway/restart.py").read_text()
    assert "HERMES_GATEWAY_RESTART_EXIT_CODES" in entrypoint
    assert 'HERMES_GATEWAY_RESTART_EXIT_CODES="${HERMES_GATEWAY_RESTART_EXIT_CODES:-all}"' in entrypoint
    assert 'if [ "$HERMES_GATEWAY_RESTART_EXIT_CODES" = "all" ]; then' in entrypoint
    assert "run_gateway_supervisor" in entrypoint
    assert "Hermes gateway requested restart" in entrypoint
    assert "wait -n" not in entrypoint


def test_enclava_first_boot_supports_inference_env_names():
    entrypoint = (ROOT / "docker/entrypoint-enclava.sh").read_text()
    docs = (ROOT / "docs/ENCLAVA_PLATFORM.md").read_text()

    assert "HERMES_INFERENCE_PROVIDER" in entrypoint
    assert "HERMES_INFERENCE_MODEL" in entrypoint
    assert "HERMES_INFERENCE_PROVIDER" in docs
    assert "HERMES_INFERENCE_MODEL" in docs
    assert "LLM_MODEL" not in docs


def test_enclava_cap_v1_docs_and_config_are_dashboard_public():
    paths = [
        ROOT / "Dockerfile.enclava",
        ROOT / "docker/enclava-config.yaml",
        ROOT / "docs/ENCLAVA_PLATFORM.md",
    ]

    for path in paths:
        assert "dashboard" in path.read_text().lower(), f"{path} should describe dashboard support"

    entrypoint = (ROOT / "docker/entrypoint-enclava.sh").read_text()
    config = (ROOT / "docker/enclava-config.yaml").read_text()
    docs = (ROOT / "docs/ENCLAVA_PLATFORM.md").read_text()

    assert "unset HERMES_DASHBOARD" not in entrypoint
    assert "dashboard" in config.lower()
    assert "API-only" not in docs
    assert "127.0.0.1:18080" in docs
    assert "/v1" not in docs


def test_enclava_build_workflow_smoke_tests_dashboard_not_public_api():
    workflow = (ROOT / ".github/workflows/enclava-build.yml").read_text()

    assert "HERMES_DASHBOARD_AUTH_TOKEN=test-dashboard-secret" in workflow
    assert "http://127.0.0.1:18000/health" in workflow
    assert "http://127.0.0.1:18000/v1/models" not in workflow


def test_enclava_build_workflow_validates_prs_without_latest_tag():
    workflow = (ROOT / ".github/workflows/enclava-build.yml").read_text()

    assert "pull_request:" in workflow
    assert "type=raw,value=latest" not in workflow


def test_enclava_build_workflow_cosign_signs_pushed_image():
    workflow = (ROOT / ".github/workflows/enclava-build.yml").read_text()

    assert "Cosign sign image" in workflow
    assert "cosign sign --yes" in workflow
    assert "${{ steps.policy_meta.outputs.image_ref }}" in workflow
