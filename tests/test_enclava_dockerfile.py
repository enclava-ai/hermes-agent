from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_enclava_dockerfile_installs_existing_extras():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    extras = pyproject["project"]["optional-dependencies"]
    dockerfile = (ROOT / "Dockerfile.enclava").read_text()

    assert ".[dashboard]" not in dockerfile
    assert ".[web" not in dockerfile
    assert ".[homeassistant]" in dockerfile
    assert "homeassistant" in extras


def test_enclava_dockerfile_provides_wait_exec_helper():
    dockerfile = (ROOT / "Dockerfile.enclava").read_text()

    assert "docker/enclava-wait-exec" in dockerfile
    assert "/usr/local/bin/enclava-wait-exec" in dockerfile


def test_enclava_dockerfile_uses_pid1_init():
    dockerfile = (ROOT / "Dockerfile.enclava").read_text()

    assert "tini" in dockerfile
    assert (
        'ENTRYPOINT ["/usr/bin/tini", "-g", "--", '
        '"/opt/hermes/docker/entrypoint-enclava-api.sh"]'
    ) in dockerfile


def test_enclava_descriptor_uses_pid1_init_command():
    descriptor = tomllib.loads((ROOT / "enclava.toml").read_text())

    assert descriptor["app"]["command"] == [
        "/usr/bin/tini",
        "-g",
        "--",
        "/opt/hermes/docker/entrypoint-enclava-api.sh",
    ]


def test_enclava_package_uses_state_directly_without_app_bind_mounts():
    descriptor = tomllib.loads((ROOT / "enclava.toml").read_text())
    dockerfile = (ROOT / "Dockerfile.enclava").read_text()
    entrypoint = (ROOT / "docker/entrypoint-enclava-api.sh").read_text()
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
    entrypoint = (ROOT / "docker/entrypoint-enclava-api.sh").read_text()

    assert "ENCLAVA_CONTAINER_NAME" in entrypoint
    assert "HERMES_ENCLAVA_WAIT_EXEC_DONE" in entrypoint
    assert 'exec /usr/local/bin/enclava-wait-exec "$0" "$@"' in entrypoint


def test_enclava_entrypoint_requires_api_key_for_public_bind():
    entrypoint = (ROOT / "docker/entrypoint-enclava-api.sh").read_text()

    assert "API_SERVER_HOST" in entrypoint
    assert "API_SERVER_KEY" in entrypoint
    assert "0.0.0.0" in entrypoint
    assert "API_SERVER_KEY is required" in entrypoint


def test_enclava_entrypoint_does_not_delegate_to_standard_docker_entrypoint():
    entrypoint = (ROOT / "docker/entrypoint-enclava-api.sh").read_text()

    assert "/opt/hermes/docker/entrypoint.sh" not in entrypoint
    assert "exec hermes gateway" in entrypoint


def test_enclava_first_boot_supports_inference_env_names():
    entrypoint = (ROOT / "docker/entrypoint-enclava-api.sh").read_text()
    docs = (ROOT / "docs/ENCLAVA_PLATFORM.md").read_text()

    assert "HERMES_INFERENCE_PROVIDER" in entrypoint
    assert "HERMES_INFERENCE_MODEL" in entrypoint
    assert "HERMES_INFERENCE_PROVIDER" in docs
    assert "HERMES_INFERENCE_MODEL" in docs
    assert "LLM_MODEL" not in docs


def test_enclava_cap_v1_docs_and_config_are_api_only():
    paths = [
        ROOT / "Dockerfile.enclava",
        ROOT / "docker/enclava-config.yaml",
        ROOT / "docs/ENCLAVA_PLATFORM.md",
    ]

    for path in paths:
        assert "dashboard" not in path.read_text().lower(), f"{path} should not claim dashboard support"

    entrypoint = (ROOT / "docker/entrypoint-enclava-api.sh").read_text()
    config = (ROOT / "docker/enclava-config.yaml").read_text()
    docs = (ROOT / "docs/ENCLAVA_PLATFORM.md").read_text()

    assert "unset HERMES_DASHBOARD" in entrypoint
    assert "API-only" in config
    assert "API-only" in docs


def test_enclava_build_workflow_validates_prs_without_latest_tag():
    workflow = (ROOT / ".github/workflows/enclava-build.yml").read_text()

    assert "pull_request:" in workflow
    assert "type=raw,value=latest" not in workflow


def test_enclava_build_workflow_cosign_signs_pushed_image():
    workflow = (ROOT / ".github/workflows/enclava-build.yml").read_text()

    assert "Cosign sign image" in workflow
    assert "cosign sign --yes" in workflow
    assert "${{ steps.policy_meta.outputs.image_ref }}" in workflow
