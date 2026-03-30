# Coding Conventions

**Analysis Date:** 2026-03-30

## Naming Patterns

**Files:**
- `snake_case.py` for all Python files: `run_agent.py`, `model_tools.py`, `hermes_state.py`
- Test files prefixed with `test_`: `test_plugins.py`, `test_atomic_json_write.py`
- Test files named after the module they test: `test_toolsets.py` tests `toolsets.py`

**Functions:**
- `snake_case` for all functions: `atomic_json_write`, `_strip_provider_prefix`, `build_session_context`
- Private/internal functions prefixed with `_`: `_isolate_hermes_home`, `_hash_sender_id`, `_get_disabled_plugins`
- Helper functions in test files prefixed with `_`: `_make_plugin_dir`, `_patch_agent_bootstrap`, `_make_tool_defs`
- Boolean predicates named `is_*` or `_env_enabled`: `is_managed()`, `_env_enabled(name)`

**Classes:**
- `PascalCase`: `AIAgent`, `ContextCompressor`, `PluginManager`, `SessionSource`, `HermesACPAgent`
- Test classes prefixed with `Test`: `TestShouldCompress`, `TestAtomicJsonWrite`, `TestPluginDiscovery`
- Error classes named `*Error` or named descriptively when faking SDK types: `_RateLimitError`, `_OverloadedError`

**Variables and Constants:**
- `UPPER_SNAKE_CASE` for module-level constants: `VALID_HOOKS`, `ENTRY_POINTS_GROUP`, `DISK_USAGE_WARNING_THRESHOLD_GB`
- Private module-level constants prefixed with `_`: `_PROVIDER_PREFIXES`, `_OLLAMA_TAG_PATTERN`, `_EXTRA_ENV_KEYS`
- `snake_case` for local variables and instance attributes

## Code Style

**Formatting:**
- No formatter config detected (no `.prettierrc`, `biome.json`, `pyproject.toml [tool.black]`). Code follows PEP 8 conventions manually.
- 4-space indentation throughout.
- Lines kept readable; long imports sometimes split with parentheses.

**Linting:**
- `noqa` comments used selectively for intentional suppressions: `# noqa: F401 — re-exported`, `# noqa: E402, F401`
- `type: ignore[assignment]` used when optional SDK is assigned `None` as a sentinel for deferred import
- No `.flake8`, `.ruff.toml`, or equivalent config found in repo root

**Type Annotations:**
- `from typing import Dict, List, Optional, Any` in files targeting Python 3.9 compatibility
- `from __future__ import annotations` used in newer modules (`acp_adapter/`, `agent/smart_model_routing.py`, `gateway/stream_consumer.py`) to enable PEP 563 deferred evaluation
- Modern union syntax (`str | None`) used alongside the `Optional[str]` form — not yet unified
- `typing.Union` used in `utils.py` for cross-version safety

## Import Organization

**Order (observed pattern):**
1. `from __future__ import annotations` (if used)
2. Standard library imports (alphabetical within group)
3. Third-party imports
4. Local project imports (absolute)
5. Intra-package relative imports (in subpackages like `gateway/`)

**Example (`gateway/session.py`):**
```python
import hashlib
import logging
import os
import json
# ...
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from .config import Platform, GatewayConfig, SessionResetPolicy, HomeChannel
```

**Path Aliases:**
- No path aliases (`@/`, `~/`). All imports use absolute module paths from the project root (which is on `sys.path`).

**Deferred/Guarded Imports:**
- Optional SDK dependencies imported inside `try/except ImportError` blocks and set to `None` on failure: `yaml = None`, `web = None`
- Presence checks use inline imports marked `# noqa: F401 — SDK presence check`
- Heavy optional imports deferred inside functions to avoid import-time cost

## Error Handling

**Patterns:**
- Specific exception types caught rather than bare `except Exception` where possible
- `except BaseException` used intentionally in cleanup paths to catch `KeyboardInterrupt`/`SystemExit` before re-raising: see `utils.atomic_json_write`
- Non-critical failures logged at `DEBUG` level and swallowed (never silently lost): `logger.debug("Session DB operation failed: %s", e)`
- Critical path errors bubble up; peripheral errors (session DB, temp file cleanup) are caught-and-logged
- `raise` (bare) always used after cleanup to re-raise the original exception

```python
# Standard cleanup pattern in utils.py
try:
    os.unlink(tmp_path)
except OSError:
    pass
raise
```

**Custom error faking in tests:**
- Error classes defined locally in test files to simulate SDK-specific exceptions with `status_code` attributes, avoiding SDK imports in tests

## Logging

**Framework:** `logging` (stdlib), configured via `logging.getLogger(__name__)` at module level

**Patterns:**
- Every module obtains its logger at the top: `logger = logging.getLogger(__name__)`
- `logger.info(...)` for startup/lifecycle events
- `logger.debug(...)` for recoverable errors and non-critical failures
- `logger.warning(...)` for data quality issues (e.g., malformed JSON)
- `%s`-style format strings used (not f-strings) to defer string formatting: `logger.debug("Failed %s: %s", path, e)`

## Comments and Documentation

**Module Docstrings:**
- All modules start with a triple-quoted docstring describing purpose, features, and usage
- Longer modules use section headers within the docstring (e.g., `Lifecycle hooks`, `Tool registration`)

**Function Docstrings:**
- Public utility functions use Google-style docstrings with `Args:` and `Returns:` sections
- Internal functions use single-line or brief multi-line docstrings

**Section Separators:**
- Two styles used depending on file age and author:
  - `# ---------------------------------------------------------------------------` (older style)
  - `# ── Section Name ─────────────────────────────────────────────────────────` (newer style, Unicode box-drawing)
  - `# =============================================================================` (major section breaks)

**Inline Comments:**
- Inline `# noqa` annotations always include a reason: `# noqa: F401 — re-exported`
- `# type: ignore[assignment]` used with specific error code

## Module and Class Design

**Exports:**
- No `__all__` in most modules; explicit imports are preferred
- Re-exports annotated with `# noqa: F401 — re-exported` at the import site

**Dataclasses:**
- `@dataclass` used for data-carrier types: `SessionSource`, `ContextReference`
- `@dataclass(frozen=True)` used for immutable value objects
- `SimpleNamespace` used extensively to build mock/fake SDK response objects in both production adapters and tests

**Constants Pattern:**
- Module-level `frozenset` used for membership sets: `_PROVIDER_PREFIXES: frozenset[str] = frozenset({...})`
- `re.compile(...)` at module level for reused patterns: `_PHONE_RE = re.compile(...)`

**Optional Dependencies Pattern:**
```python
try:
    import yaml
except ImportError:  # pragma: no cover – yaml is optional at import time
    yaml = None  # type: ignore[assignment]
```

---

*Convention analysis: 2026-03-30*
