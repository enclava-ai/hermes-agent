<!-- GSD:project-start source:PROJECT.md -->
## Project

**Hermes Web Dashboard**

A web-based configuration dashboard for Hermes Agent that lets users set up, configure, and manage their Hermes instance through a browser instead of editing YAML files and running CLI commands. Includes a first-run onboarding wizard and an ongoing settings management interface. Built as a self-contained addition to the existing codebase — no modifications to upstream files.

**Core Value:** Users can fully configure and onboard Hermes Agent through a browser without touching config files or CLI commands.

### Constraints

- **Upstream compatibility**: No modifications to existing files — dashboard is a new self-contained module
- **Tech stack**: Vanilla HTML/JS/CSS frontend, no Node.js build tooling — served as static files
- **Auth**: Simple username/password login (not OAuth, not API key)
- **Deployment**: Must work in all existing deployment modes (local, Docker, NixOS, Enclava)
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11+ - Core agent logic, all tools, gateway, CLI, RL environments
- JavaScript/Node.js 18+ - Browser automation runner (`agent-browser` npm package), WhatsApp bridge scripts
- Nix (Flake) - Reproducible dev environments and NixOS module packaging
## Runtime
- CPython ≥ 3.11 (required by `pyproject.toml`)
- Node.js ≥ 18.0.0 (required by `package.json` engines field)
- Python: `uv` (preferred) — lockfile at `uv.lock`; also `pip`-compatible via `pyproject.toml`
- Node.js: `npm` — lockfile at `package-lock.json`
- Nix: `flake.lock` for reproducible system environments
## Frameworks
- No web framework for main agent loop (pure asyncio + threads)
- `prompt_toolkit` 3.0.52+ - Interactive CLI REPL (`cli.py`, `hermes_cli/`)
- `rich` 14.3.3+ - Terminal rendering, panels, progress, syntax highlighting
- `pydantic` 2.12.5+ - Data validation and typed config models
- `jinja2` 3.1.5+ - Prompt/template rendering
- `fire` 0.7.1+ - CLI entrypoint argument parsing (`run_agent.py`, `rl_cli.py`)
- `tenacity` 9.1.4+ - Retry logic for LLM API calls
- `aiohttp` 3.13.3+ - HTTP server/client for webhooks (SMS, Mattermost, Home Assistant, Signal)
- `asyncio` (stdlib) - Async event loop for all platform adapters
- `fastapi` 0.104.0+ - REST API server for RL environment (`rl` optional extra)
- `uvicorn[standard]` 0.24.0+ - ASGI server for FastAPI RL endpoint
- `pytest` 9.0.2+ - Test runner
- `pytest-asyncio` 1.3.0+ - Async test support
- `pytest-xdist` 3.0+ - Parallel test execution (`-n auto`)
- `setuptools` ≥ 61.0 - Build backend for `pyproject.toml`
- `uv` - Fast virtual environment + lockfile management
- Nix flake with `uv2nix` + `pyproject-nix` - NixOS packaging
## Key Dependencies
- `openai` 2.21.0–3 - Primary LLM client; all providers use OpenAI-compatible API via base_url override
- `anthropic` 0.39.0–1 - Native Anthropic SDK (`agent/anthropic_adapter.py`); required for Claude OAuth tokens and native beta features
- `httpx` 0.28.1+ - Async HTTP client for direct API calls and tool backends
- `python-dotenv` 1.2.1+ - Loads `~/.hermes/.env` at startup
- `pyyaml` 6.0.2+ - Reads `~/.hermes/config.yaml`
- `firecrawl-py` 4.16.0+ - Web search, extract, crawl (`tools/web_tools.py`)
- `exa-py` 2.9.0+ - AI-native web search (`tools/web_tools.py`)
- `parallel-web` 0.4.2+ - Parallel web search/extract (`tools/web_tools.py`)
- `fal-client` 0.13.1+ - Image generation via FAL.ai FLUX models (`tools/image_generation_tool.py`)
- `edge-tts` 7.2.7+ - Free Microsoft Edge TTS (`tools/tts_tool.py`)
- `faster-whisper` 1.0.0+ - Local speech-to-text (`tools/transcription_tools.py`)
- `PyJWT[crypto]` 2.12.0+ - GitHub App JWT auth for Skills Hub (`tools/skills_hub.py`)
- `agent-browser` 0.13.0 (npm) - Headless Chromium browser control (`tools/browser_tool.py`)
- `modal` 1.0.0+ - Modal cloud terminal backend (`[modal]`)
- `daytona` 0.148.0+ - Daytona cloud sandbox terminal backend (`[daytona]`)
- `python-telegram-bot` 22.6+ - Telegram gateway (`[messaging]`)
- `discord.py[voice]` 2.7.1+ - Discord gateway (`[messaging]`)
- `slack-bolt` 1.18.0+ + `slack-sdk` 3.27.0+ - Slack gateway (`[slack]`)
- `matrix-nio[e2e]` 0.24.0+ - Matrix/Element gateway with E2EE (`[matrix]`)
- `mcp` 1.2.0+ - Model Context Protocol client (`[mcp]`)
- `honcho-ai` 2.0.1+ - Cross-session user modeling (`[honcho]`)
- `elevenlabs` 1.0+ - Premium TTS voices (`[tts-premium]`)
- `croniter` 6.0.0+ - Cron expression parsing (`[cron]`)
- `agent-client-protocol` 0.8.1+ - ACP adapter protocol (`[acp]`)
- `sounddevice` 0.4.6+ + `numpy` - Local voice input (`[voice]`)
- `wandb` 0.15.0+ - RL experiment tracking (`[rl]`)
- `atroposlib` (git) - RL training framework (`[rl]`)
- `dingtalk-stream` 0.1.0+ - DingTalk messaging (`[dingtalk]`)
## Configuration
- Primary config: `~/.hermes/config.yaml` (YAML, mirrors `cli-config.yaml.example`)
- Secrets/keys: `~/.hermes/.env` (dotenv format, never committed)
- Home dir: `HERMES_HOME` env var (default `~/.hermes`), resolved by `hermes_constants.get_hermes_home()`
- Config structure: model provider, terminal backend, memory, compression, toolsets per platform, streaming, session reset, display/skin, MCP servers
- `pyproject.toml` - canonical dependency list and entry points
- `package.json` - Node.js browser tooling only
- `Dockerfile` - Debian 13.4 base with Python 3, Node.js, ffmpeg, Chromium (playwright)
- `Dockerfile.enclava` - Enclava platform variant
- `flake.nix` - Nix packaging for x86_64-linux, aarch64-linux, aarch64-darwin
## Platform Requirements
- Python ≥ 3.11
- Node.js ≥ 18 (for browser tools)
- `ffmpeg` (for audio format conversion in TTS)
- `ripgrep` (for file search tools)
- Optional: Nix with flakes enabled
- Runs anywhere Python ≥ 3.11 is available: local machine, SSH server, Docker, Modal cloud, Daytona cloud, Singularity/HPC
- Docker: `debian:13.4` with all deps via `docker/entrypoint.sh`
- NixOS: `flake.nix` provides a NixOS module
- Enclava: specialized container via `Dockerfile.enclava`
- Data volume: `/opt/data` (Docker) or `~/.hermes` (local)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- `snake_case.py` for all Python files: `run_agent.py`, `model_tools.py`, `hermes_state.py`
- Test files prefixed with `test_`: `test_plugins.py`, `test_atomic_json_write.py`
- Test files named after the module they test: `test_toolsets.py` tests `toolsets.py`
- `snake_case` for all functions: `atomic_json_write`, `_strip_provider_prefix`, `build_session_context`
- Private/internal functions prefixed with `_`: `_isolate_hermes_home`, `_hash_sender_id`, `_get_disabled_plugins`
- Helper functions in test files prefixed with `_`: `_make_plugin_dir`, `_patch_agent_bootstrap`, `_make_tool_defs`
- Boolean predicates named `is_*` or `_env_enabled`: `is_managed()`, `_env_enabled(name)`
- `PascalCase`: `AIAgent`, `ContextCompressor`, `PluginManager`, `SessionSource`, `HermesACPAgent`
- Test classes prefixed with `Test`: `TestShouldCompress`, `TestAtomicJsonWrite`, `TestPluginDiscovery`
- Error classes named `*Error` or named descriptively when faking SDK types: `_RateLimitError`, `_OverloadedError`
- `UPPER_SNAKE_CASE` for module-level constants: `VALID_HOOKS`, `ENTRY_POINTS_GROUP`, `DISK_USAGE_WARNING_THRESHOLD_GB`
- Private module-level constants prefixed with `_`: `_PROVIDER_PREFIXES`, `_OLLAMA_TAG_PATTERN`, `_EXTRA_ENV_KEYS`
- `snake_case` for local variables and instance attributes
## Code Style
- No formatter config detected (no `.prettierrc`, `biome.json`, `pyproject.toml [tool.black]`). Code follows PEP 8 conventions manually.
- 4-space indentation throughout.
- Lines kept readable; long imports sometimes split with parentheses.
- `noqa` comments used selectively for intentional suppressions: `# noqa: F401 — re-exported`, `# noqa: E402, F401`
- `type: ignore[assignment]` used when optional SDK is assigned `None` as a sentinel for deferred import
- No `.flake8`, `.ruff.toml`, or equivalent config found in repo root
- `from typing import Dict, List, Optional, Any` in files targeting Python 3.9 compatibility
- `from __future__ import annotations` used in newer modules (`acp_adapter/`, `agent/smart_model_routing.py`, `gateway/stream_consumer.py`) to enable PEP 563 deferred evaluation
- Modern union syntax (`str | None`) used alongside the `Optional[str]` form — not yet unified
- `typing.Union` used in `utils.py` for cross-version safety
## Import Organization
- No path aliases (`@/`, `~/`). All imports use absolute module paths from the project root (which is on `sys.path`).
- Optional SDK dependencies imported inside `try/except ImportError` blocks and set to `None` on failure: `yaml = None`, `web = None`
- Presence checks use inline imports marked `# noqa: F401 — SDK presence check`
- Heavy optional imports deferred inside functions to avoid import-time cost
## Error Handling
- Specific exception types caught rather than bare `except Exception` where possible
- `except BaseException` used intentionally in cleanup paths to catch `KeyboardInterrupt`/`SystemExit` before re-raising: see `utils.atomic_json_write`
- Non-critical failures logged at `DEBUG` level and swallowed (never silently lost): `logger.debug("Session DB operation failed: %s", e)`
- Critical path errors bubble up; peripheral errors (session DB, temp file cleanup) are caught-and-logged
- `raise` (bare) always used after cleanup to re-raise the original exception
- Error classes defined locally in test files to simulate SDK-specific exceptions with `status_code` attributes, avoiding SDK imports in tests
## Logging
- Every module obtains its logger at the top: `logger = logging.getLogger(__name__)`
- `logger.info(...)` for startup/lifecycle events
- `logger.debug(...)` for recoverable errors and non-critical failures
- `logger.warning(...)` for data quality issues (e.g., malformed JSON)
- `%s`-style format strings used (not f-strings) to defer string formatting: `logger.debug("Failed %s: %s", path, e)`
## Comments and Documentation
- All modules start with a triple-quoted docstring describing purpose, features, and usage
- Longer modules use section headers within the docstring (e.g., `Lifecycle hooks`, `Tool registration`)
- Public utility functions use Google-style docstrings with `Args:` and `Returns:` sections
- Internal functions use single-line or brief multi-line docstrings
- Two styles used depending on file age and author:
- Inline `# noqa` annotations always include a reason: `# noqa: F401 — re-exported`
- `# type: ignore[assignment]` used with specific error code
## Module and Class Design
- No `__all__` in most modules; explicit imports are preferred
- Re-exports annotated with `# noqa: F401 — re-exported` at the import site
- `@dataclass` used for data-carrier types: `SessionSource`, `ContextReference`
- `@dataclass(frozen=True)` used for immutable value objects
- `SimpleNamespace` used extensively to build mock/fake SDK response objects in both production adapters and tests
- Module-level `frozenset` used for membership sets: `_PROVIDER_PREFIXES: frozenset[str] = frozenset({...})`
- `re.compile(...)` at module level for reused patterns: `_PHONE_RE = re.compile(...)`
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- `AIAgent` (in `run_agent.py`) is the central agent class used by all surfaces (CLI, gateway, cron, ACP, batch runner)
- Platform adapters (messaging platforms) are isolated in `gateway/platforms/` behind a common `BasePlatformAdapter` ABC
- Tools self-register into a singleton `ToolRegistry` at import time — no central registration list
- Skills are file-system-based prompt bundles loaded dynamically at runtime
- All persistent state lives in `~/.hermes/` (SQLite for sessions, YAML for config, markdown for memory/skills)
## Layers
- Purpose: Accept user input and invoke AIAgent
- Location: `cli.py`, `hermes_cli/main.py`, `run_agent.py`, `acp_adapter/entry.py`, `batch_runner.py`, `rl_cli.py`
- Contains: Argument parsing, TUI/REPL, lifecycle management, profile bootstrapping
- Depends on: `agent/`, `model_tools.py`, `hermes_cli/`
- Used by: End users, CI pipelines, RL training harnesses
- Purpose: Bridge messaging platforms (Telegram, Discord, Slack, etc.) to the agent core
- Location: `gateway/`
- Contains: `GatewayRunner` (orchestrator), platform adapters, session management, delivery routing, event hooks, cron scheduler integration
- Depends on: `run_agent.AIAgent`, `gateway/platforms/`, `gateway/session.py`, `gateway/delivery.py`, `gateway/hooks.py`
- Used by: `hermes_cli/gateway.py`, `hermes gateway start`
- Purpose: Normalize inbound messages from each platform into `MessageEvent`, send formatted responses back
- Location: `gateway/platforms/` (`telegram.py`, `discord.py`, `slack.py`, `whatsapp.py`, `signal.py`, `matrix.py`, `mattermost.py`, `email.py`, `sms.py`, `dingtalk.py`, `api_server.py`, `webhook.py`, `homeassistant.py`)
- Contains: Bot clients, message parsing, image caching, token/session locking
- Depends on: `gateway/platforms/base.py` (`BasePlatformAdapter`), `gateway/session.py`, `gateway/config.py`
- Used by: `gateway/run.GatewayRunner`
- Purpose: Manage the tool-calling conversation loop, system prompt assembly, context compression, model routing
- Location: `run_agent.py` (`AIAgent` class, ~6000 lines), `agent/`
- Contains: Conversation loop, prompt building, model API calls, tool dispatch, context compression, trajectory saving, usage accounting, display helpers
- Depends on: `model_tools.py`, `agent/prompt_builder.py`, `agent/context_compressor.py`, `agent/anthropic_adapter.py`, `agent/model_metadata.py`, `hermes_state.py`
- Used by: `cli.py`, `gateway/run.py`, `cron/`, `acp_adapter/`, `batch_runner.py`
- Purpose: Modular helpers extracted from the monolithic agent class
- Location: `agent/`
- Contains:
- Purpose: Modular capabilities exposed to the LLM as function-call tools
- Location: `tools/`, `model_tools.py`, `toolsets.py`
- Contains: 40+ tool modules, a singleton `ToolRegistry`, toolset grouping definitions
- Pattern: Each `tools/*.py` calls `registry.register(name, toolset, schema, handler, ...)` at module import time; `model_tools.py` triggers discovery by importing all tool modules
- Depends on: `tools/registry.py`
- Used by: `run_agent.AIAgent` via `model_tools.handle_function_call()`
- Purpose: User-extensible prompt bundles that inject domain knowledge into the system prompt
- Location: `skills/` (bundled), `~/.hermes/skills/` (user), `tools/skills_tool.py`, `agent/skill_utils.py`
- Contains: Category directories, each skill as a directory with `SKILL.md` (YAML frontmatter + markdown instructions), optional `references/`, `templates/`, `assets/`
- Depends on: `agent/prompt_builder.build_skills_system_prompt()`
- Used by: `AIAgent._build_system_prompt()`, `tools/skill_manager_tool.py`
- Purpose: Persist conversation history, session metadata, and search index
- Location: `hermes_state.py` (`SessionDB`), `gateway/session.py` (`SessionStore`, `SessionContext`)
- Contains: SQLite with WAL mode, FTS5 full-text search, session chaining for compressed sessions
- Depends on: `hermes_constants.get_hermes_home()`
- Used by: `cli.py`, `gateway/run.GatewayRunner`, `tools/session_search_tool.py`
- Purpose: CLI command implementations, configuration, auth, and setup
- Location: `hermes_cli/`
- Contains: `main.py` (entry point/argument dispatch), `config.py` (YAML config management), `auth.py` (multi-provider auth), `runtime_provider.py` (provider resolution), `profiles.py` (isolated HERMES_HOME profiles), `gateway.py` (gateway service management), `cron.py` (cron job management), `plugins.py`/`plugins_cmd.py` (optional skills management), `doctor.py` (dependency checker), `setup.py` (setup wizard), `skin_engine.py`, `banner.py`
- Depends on: `hermes_constants.py`, `hermes_state.py`
- Used by: `hermes_cli/main.py`, `cli.py`, `gateway/run.py`
- Purpose: Schedule recurring agent tasks with delivery routing
- Location: `cron/`
- Contains: `scheduler.py` (APScheduler-based), `jobs.py` (job definitions), `__init__.py`
- Depends on: `run_agent.AIAgent`, `gateway/delivery.py`
- Used by: `gateway/run.GatewayRunner`, `hermes cron` commands
- Purpose: Expose Hermes as an Agent Communication Protocol (ACP) server for editor integration
- Location: `acp_adapter/`
- Contains: `entry.py` (CLI entry), `server.py` (ACP JSON-RPC server), `session.py`, `tools.py`, `events.py`, `permissions.py`
- Depends on: `run_agent.AIAgent`
- Used by: `hermes acp`, editor integrations
## Data Flow
- Conversation history: in-memory list of OpenAI-format dicts, serialized to disk between turns (gateway) or kept in-process (CLI)
- Session database: `~/.hermes/state.db` (SQLite WAL, FTS5)
- Memory: `~/.hermes/MEMORY.md` (markdown, updated by `memory` tool)
- Config: `~/.hermes/config.yaml` (YAML, read at gateway startup and per agent run)
- Context compression: triggered automatically when approaching context limit; uses auxiliary cheap model to summarize middle turns; resulting summary prepended as synthetic message
## Key Abstractions
- Purpose: The universal agent class. All surfaces instantiate this to run conversations.
- Pattern: Stateful object (holds message history, session config), but `run_conversation()` is the external API. Callbacks (`tool_progress_callback`, `stream_delta_callback`, `step_callback`) decouple the display layer from the agent loop.
- Purpose: ABC for all messaging platform integrations
- Pattern: Subclasses implement `start()`, `stop()`, and async message handling. Platforms lock per-session tokens to serialize concurrent messages.
- Purpose: Singleton collecting all tool schemas and handlers
- Pattern: Tool files call `registry.register()` at module import time. `model_tools.py` imports all tool modules to trigger registration, then queries the registry.
- Purpose: Tracks where a message came from (`SessionSource`) and all conversation state for a given chat
- Pattern: Keyed by `(platform, chat_id, thread_id)` tuple; stored as JSONL files in `~/.hermes/sessions/`
- Purpose: Routes agent output to correct platform/channel
- Pattern: Parses target strings like `"telegram:123456"`, `"origin"`, `"local"` into `DeliveryTarget` dataclasses
- Purpose: Event-driven lifecycle hooks at `gateway:startup`, `session:start/end`, `agent:start/step/end`, `command:*`
- Pattern: Hook handlers are Python files discovered in `~/.hermes/hooks/` with a `HOOK.yaml` descriptor
- Purpose: Thread-safe iteration counter with per-agent cap (parent: 90, subagent: 50)
- Pattern: Prevents runaway tool-calling loops; shared between parent and subagent when needed
## Entry Points
- Location: `cli.py`, invoked as `hermes` or `hermes chat`
- Triggers: Direct user invocation
- Responsibilities: TUI REPL, command routing, session management, profile selection, tool display
- Location: `hermes_cli/main.py`
- Triggers: `hermes <subcommand>`
- Responsibilities: Routes `hermes gateway`, `hermes cron`, `hermes setup`, `hermes doctor`, `hermes sessions browse`, `hermes acp`, `hermes profile`, `hermes honcho`, etc.
- Location: `gateway/run.py`, class `GatewayRunner`
- Triggers: `hermes gateway` or systemd service
- Responsibilities: Start all configured platform adapters, route messages to agent, manage session lifecycle, run cron scheduler
- Location: `acp_adapter/entry.py`
- Triggers: `hermes acp` or `hermes-acp`
- Responsibilities: JSON-RPC stdio transport for editor integration (ACP protocol)
- Location: `batch_runner.py`
- Triggers: Direct invocation for RL/eval workloads
- Responsibilities: Run multiple agent conversations in parallel for training data generation
## Error Handling
- Tool errors are returned as error strings to the model (not raised); model decides how to recover
- Gateway hooks catch all handler exceptions — hook failures never block message delivery
- Platform adapter connection failures are retried with exponential backoff in background
- Context overflow triggers automatic compression rather than hard failure
- `_SafeWriter` wraps stdout/stderr to absorb `OSError`/`ValueError` from broken pipes in headless/daemon mode
- `IterationBudget` caps runaway loops with a graceful stop message
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
