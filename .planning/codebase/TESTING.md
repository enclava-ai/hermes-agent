# Testing Patterns

**Analysis Date:** 2026-03-30

## Test Framework

**Runner:**
- `pytest` >= 9.0.2
- Config: `pyproject.toml` under `[tool.pytest.ini_options]`

**Plugins:**
- `pytest-asyncio` >= 1.3.0 — async test support
- `pytest-xdist` >= 3.0 — parallel test execution

**Assertion Library:**
- pytest built-in `assert` statements — no separate assertion library

**Run Commands:**
```bash
pytest                          # Run all non-integration tests (default)
pytest -m integration           # Run only integration tests
pytest tests/test_plugins.py    # Run a specific test file
pytest -n auto                  # Run in parallel (default via addopts)
pytest -n 0                     # Disable parallelism (for debugging)
pytest -k "test_session"        # Run tests matching name pattern
```

## Test File Organization

**Location:**
- All tests live under `tests/`
- Subdirectories mirror the package structure:
  - `tests/agent/` — tests for `agent/` package
  - `tests/gateway/` — tests for `gateway/` package
  - `tests/hermes_cli/` — tests for `hermes_cli/` package
  - `tests/tools/` — tests for `tools/` package
  - `tests/acp/` — tests for `acp_adapter/` package
  - `tests/skills/` — tests for optional `skills/`
  - `tests/integration/` — integration tests requiring external services
  - `tests/fakes/` — shared fake servers (e.g., `fake_ha_server.py`)
- Top-level test files (`tests/test_*.py`) test top-level modules: `run_agent.py`, `toolsets.py`, `utils.py`

**Naming:**
- Files: `test_{module_name}.py` or `test_{bug_number}_{description}.py`
  - `test_toolsets.py`, `test_atomic_json_write.py`
  - `test_1630_context_overflow_loop.py`, `test_413_compression.py`, `test_860_dedup.py` (regression tests named by issue/PR number)

**Structure:**
```
tests/
├── conftest.py          # Global fixtures (autouse isolation, timeouts)
├── fakes/               # Shared fake servers
├── integration/         # External-service tests (marked integration)
├── agent/               # Mirrors agent/ package
├── gateway/             # Mirrors gateway/ package
├── hermes_cli/          # Mirrors hermes_cli/ package
├── tools/               # Mirrors tools/ package
├── acp/                 # Mirrors acp_adapter/ package
├── skills/              # Skill-specific tests
└── test_*.py            # Top-level module tests
```

## Test Structure

**Suite Organization:**
```python
"""Module-level docstring explaining what is under test."""

import pytest
from unittest.mock import patch, MagicMock

from mymodule import MyClass


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_something(...) -> ...:
    """Private factory helper used by multiple test classes."""
    ...


# ── TestFeatureA ──────────────────────────────────────────────────────────

class TestFeatureA:
    """Tests for a specific feature or method group."""

    def test_happy_path(self):
        """Descriptive sentence about what this test verifies."""
        result = MyClass().do_thing()
        assert result == expected

    def test_edge_case(self):
        """Edge case description."""
        ...
```

**Patterns:**
- Classes group related tests: `TestShouldCompress`, `TestPluginDiscovery`, `TestAtomicJsonWrite`
- Test method names are descriptive sentences: `test_orphaned_result_removed`, `test_discover_is_idempotent`
- Standalone test functions (not in a class) used for simple or regression tests: `test_anthropic_cache_read_and_creation_added`
- Unicode box-drawing separators (`# ── Section ─────`) used to visually separate test classes within a file

## Mocking

**Framework:** `unittest.mock` (`MagicMock`, `AsyncMock`, `patch`, `patch.object`)

**Patterns:**

Context manager patching for tight scope:
```python
@patch("run_agent.AIAgent._create_request_openai_client")
@patch("run_agent.AIAgent._close_request_openai_client")
def test_text_only_response(self, mock_close, mock_create):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter(chunks)
    mock_create.return_value = mock_client
    ...
```

`monkeypatch` for replacing module-level attributes without cleanup:
```python
def test_something(monkeypatch):
    monkeypatch.setattr(run_agent, "get_tool_definitions", lambda **kwargs: [...])
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes_test"))
    monkeypatch.delenv("HERMES_SESSION_PLATFORM", raising=False)
```

`patch` as decorator stack (decorators apply bottom-up, args left-to-right):
```python
with (
    patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
    patch("run_agent.check_toolset_requirements", return_value={}),
    patch("run_agent.OpenAI"),
):
    ...
```

**SimpleNamespace as fake SDK objects:**
```python
# Build a fake OpenAI-shaped response without importing the SDK
response = SimpleNamespace(
    choices=[SimpleNamespace(
        message=SimpleNamespace(content="Hello", tool_calls=None),
        finish_reason="stop",
    )],
    usage=SimpleNamespace(prompt_tokens=10, completion_tokens=3),
)
```

**Fake error classes to simulate SDK exceptions:**
```python
class _RateLimitError(Exception):
    def __init__(self):
        super().__init__("Error code: 429 - Rate limit exceeded.")
        self.status_code = 429
```

**Blocking optional SDK imports at test collection time:**
```python
import sys, types
sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())
```

**What to Mock:**
- External API clients (OpenAI, Anthropic SDKs)
- File system calls when testing non-FS logic
- `time.sleep`, `signal`, subprocess calls in unit tests
- `HERMES_HOME` environment variable (always, via autouse fixture)

**What NOT to Mock:**
- The function under test itself
- Filesystem operations when testing atomic write behavior — use `tmp_path` instead
- Subprocess calls in worktree tests — they run real `git` commands on a temp repo

## Fixtures and Factories

**Global (conftest.py):**

```python
@pytest.fixture(autouse=True)
def _isolate_hermes_home(tmp_path, monkeypatch):
    """Redirect HERMES_HOME to temp dir — runs for every test."""
    fake_home = tmp_path / "hermes_test"
    fake_home.mkdir()
    (fake_home / "sessions").mkdir()
    # ... etc
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

@pytest.fixture(autouse=True)
def _enforce_test_timeout():
    """Kill tests exceeding 30 seconds via SIGALRM (Unix only)."""
    signal.alarm(30)
    yield
    signal.alarm(0)

@pytest.fixture()
def mock_config():
    """Minimal hermes config dict for unit tests."""
    return {"model": "test/mock-model", "toolsets": ["terminal", "file"], ...}
```

**Local fixture pattern:**
```python
@pytest.fixture()
def agent():
    """Minimal AIAgent with mocked OpenAI client."""
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        a = AIAgent(api_key="test-key-1234567890", quiet_mode=True, skip_context_files=True, skip_memory=True)
        a.client = MagicMock()
        return a
```

**Factory helpers (module-level private functions):**
```python
def _make_tool_defs(*names: str) -> list:
    """Build minimal tool definition list accepted by AIAgent.__init__."""
    ...

def _make_plugin_dir(base: Path, name: str, *, register_body: str = "pass", manifest_extra: dict | None = None) -> Path:
    """Create a minimal plugin directory with plugin.yaml + __init__.py."""
    ...
```

**Test data location:**
- No separate fixtures directory. Test data is built inline via factory helpers or `tmp_path`.
- `tests/fakes/fake_ha_server.py` provides a reusable fake Home Assistant HTTP server.

## Coverage

**Requirements:** Not enforced (no `--cov` in `addopts`, no coverage threshold config)

**View Coverage:**
```bash
pytest --cov=. --cov-report=html     # Generate HTML coverage report
pytest --cov=agent --cov-report=term # Terminal report for agent/ package
```

## Test Types

**Unit Tests:**
- Scope: single function, method, or class in isolation
- Location: `tests/test_*.py` and `tests/{package}/test_*.py`
- All external calls mocked
- Run by default (`pytest` with no flags)

**Integration Tests:**
- Scope: real external services (Firecrawl, Modal, Home Assistant, voice hardware)
- Location: `tests/integration/`
- Marked with `@pytest.mark.integration` or module-level `pytestmark = pytest.mark.integration`
- Excluded from default run: `addopts = "-m 'not integration'"`
- Run explicitly: `pytest -m integration`

**End-to-End Tests:**
- Not a separate formal category. Gateway tests in `tests/gateway/` test full platform flows (Telegram, Discord, Slack, etc.) but use mocked platform SDKs.

**Regression Tests:**
- Named with issue/PR numbers: `test_1630_context_overflow_loop.py`, `test_413_compression.py`
- Include a docstring explaining the original bug

## Common Patterns

**Async Testing:**
```python
# Use @pytest.mark.asyncio on individual async test methods
class TestInitialize:
    @pytest.mark.asyncio
    async def test_initialize_returns_correct_protocol_version(self, agent):
        resp = await agent.initialize(protocol_version=1)
        assert isinstance(resp, InitializeResponse)

# AsyncMock for coroutine return values
mock_fn = AsyncMock(return_value=some_value)
```

**Error Testing:**
```python
def test_invalid_platform_raises(self):
    with pytest.raises((ValueError, KeyError)):
        SessionSource.from_dict({"platform": "nonexistent", "chat_id": "1"})

def test_preserves_original_on_serialization_error(self, tmp_path):
    with pytest.raises(TypeError):
        atomic_json_write(target, {"bad": object()})
    # Verify side-effect: original file unchanged
    assert json.loads(target.read_text()) == original
```

**Filesystem Testing (use `tmp_path`):**
```python
def test_creates_parent_directories(self, tmp_path):
    target = tmp_path / "deep" / "nested" / "dir" / "data.json"
    atomic_json_write(target, {"ok": True})
    assert target.exists()
```

**Environment isolation (use `monkeypatch`):**
```python
def test_discover_project_plugins(self, tmp_path, monkeypatch):
    monkeypatch.chdir(project_dir)
    monkeypatch.setenv("HERMES_ENABLE_PROJECT_PLUGINS", "true")
```

**Skipping on missing optional deps:**
```python
try:
    from environments.agent_loop import HermesAgentLoop
except ImportError:
    pytest.skip("atroposlib not installed", allow_module_level=True)
```

**Concurrency Testing:**
```python
def test_concurrent_writes_dont_corrupt(self, tmp_path):
    errors = []
    def writer(n):
        try:
            atomic_json_write(target, {"writer": n, "data": list(range(100))})
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert not errors
```

---

*Testing analysis: 2026-03-30*
