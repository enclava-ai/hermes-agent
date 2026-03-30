# Codebase Structure

**Analysis Date:** 2026-03-30

## Directory Layout

```
hermes-agent/
├── cli.py                     # Interactive CLI entry point (TUI REPL)
├── run_agent.py               # AIAgent class — universal agent loop (~6000 lines)
├── model_tools.py             # Tool discovery/dispatch orchestration layer
├── toolsets.py                # Toolset grouping definitions and resolution
├── hermes_constants.py        # Shared constants (HERMES_HOME, URLs) — no deps
├── hermes_state.py            # SQLite session store (WAL, FTS5)
├── hermes_time.py             # Timezone utilities
├── utils.py                   # Atomic file write helpers
├── batch_runner.py            # Parallel agent runner for RL/eval workloads
├── rl_cli.py                  # RL training CLI entry point
├── mini_swe_runner.py         # SWE benchmark runner
├── trajectory_compressor.py   # Trajectory post-processing
├── toolset_distributions.py   # Toolset frequency analysis for training
├── pyproject.toml             # Python package metadata and entry points
├── requirements.txt           # Pip dependencies
├── flake.nix / nix/           # NixOS packaging
├── Dockerfile                 # Standard container image
├── Dockerfile.enclava         # Enclava platform container image
│
├── agent/                     # Agent support modules (extracted from run_agent.py)
│   ├── anthropic_adapter.py   # Anthropic Messages API translation layer
│   ├── auxiliary_client.py    # Lightweight LLM client for side tasks
│   ├── context_compressor.py  # Automatic context window compression
│   ├── context_references.py  # Context file tracking
│   ├── copilot_acp_client.py  # GitHub Copilot ACP client
│   ├── display.py             # Tool progress messages, spinners, emoji
│   ├── insights.py            # Usage insights tracking
│   ├── model_metadata.py      # Context length probing, token estimation
│   ├── models_dev.py          # Developer model list overrides
│   ├── prompt_builder.py      # Stateless system prompt assembly
│   ├── prompt_caching.py      # Anthropic prompt cache control injection
│   ├── redact.py              # Secret redaction from tool outputs
│   ├── skill_commands.py      # Slash command handling (shared CLI+gateway)
│   ├── skill_utils.py         # Skill file parsing utilities
│   ├── smart_model_routing.py # Cheap-vs-strong model routing
│   ├── title_generator.py     # Auto session title generation
│   ├── trajectory.py          # Trajectory/replay saving (ShareGPT format)
│   └── usage_pricing.py       # Token cost estimation across providers
│
├── gateway/                   # Messaging platform gateway
│   ├── run.py                 # GatewayRunner — main gateway controller (~5000 lines)
│   ├── session.py             # SessionStore, SessionContext, SessionSource
│   ├── delivery.py            # DeliveryRouter — routes output to platforms
│   ├── hooks.py               # HookRegistry — lifecycle event system
│   ├── config.py              # GatewayConfig, Platform enum, HomeChannel
│   ├── mirror.py              # Cross-platform message mirroring
│   ├── pairing.py             # DM pairing store (code-based user auth)
│   ├── status.py              # Gateway status reporting
│   ├── sticker_cache.py       # Platform sticker/reaction caching
│   ├── stream_consumer.py     # Streaming response consumer
│   ├── channel_directory.py   # Channel lookup helpers
│   ├── builtin_hooks/         # Always-active built-in hook handlers
│   └── platforms/             # Platform adapter implementations
│       ├── base.py            # BasePlatformAdapter ABC, MessageEvent, image cache
│       ├── telegram.py        # Telegram Bot API adapter
│       ├── discord.py         # Discord adapter
│       ├── slack.py           # Slack adapter
│       ├── whatsapp.py        # WhatsApp adapter
│       ├── signal.py          # Signal adapter
│       ├── matrix.py          # Matrix adapter
│       ├── mattermost.py      # Mattermost adapter
│       ├── email.py           # Email adapter
│       ├── sms.py             # SMS adapter
│       ├── dingtalk.py        # DingTalk adapter
│       ├── homeassistant.py   # Home Assistant adapter
│       ├── api_server.py      # REST API server adapter
│       ├── webhook.py         # Generic webhook adapter
│       └── ADDING_A_PLATFORM.md  # Guide for new platform adapters
│
├── tools/                     # Tool implementations (self-registering)
│   ├── registry.py            # ToolRegistry singleton
│   ├── terminal_tool.py       # Shell execution (local/Docker/Modal/SSH/Daytona)
│   ├── file_tools.py          # read_file, write_file, search_files
│   ├── file_operations.py     # Low-level file operation helpers
│   ├── web_tools.py           # web_search, web_extract
│   ├── browser_tool.py        # Browser automation (navigate, click, type, etc.)
│   ├── browser_providers/     # Browser backend implementations
│   ├── vision_tools.py        # Image analysis
│   ├── image_generation_tool.py  # Image generation
│   ├── memory_tool.py         # MEMORY.md read/write
│   ├── todo_tool.py           # Todo list management
│   ├── delegate_tool.py       # Subagent delegation (spawns child AIAgent)
│   ├── mixture_of_agents_tool.py  # MoA parallel querying
│   ├── mcp_tool.py            # MCP (Model Context Protocol) tool integration
│   ├── skills_tool.py         # skills_list, skill_view
│   ├── skill_manager_tool.py  # skill_manage (install/uninstall/enable/disable)
│   ├── skills_hub.py          # Skills Hub registry client
│   ├── skills_sync.py         # Skills sync with remote registry
│   ├── skills_guard.py        # Skill execution safety checks
│   ├── send_message_tool.py   # Cross-platform message sending
│   ├── session_search_tool.py # Full-text search across session history
│   ├── cronjob_tools.py       # Cron job management tools
│   ├── clarify_tool.py        # Clarifying question tool
│   ├── code_execution_tool.py # execute_code tool
│   ├── delegate_tool.py       # delegate_task tool (subagent spawning)
│   ├── homeassistant_tool.py  # Home Assistant smart home tools
│   ├── honcho_tools.py        # Honcho AI memory tools
│   ├── tts_tool.py            # Text-to-speech tool
│   ├── transcription_tools.py # Audio transcription tools
│   ├── voice_mode.py          # Voice mode management
│   ├── approval.py            # Interactive exec approval system
│   ├── checkpoint_manager.py  # Session checkpoint snapshots
│   ├── interrupt.py           # Agent interrupt control
│   ├── process_registry.py    # Background process tracking
│   ├── openrouter_client.py   # OpenRouter API client
│   ├── mcp_oauth.py           # MCP OAuth flow
│   ├── credential_files.py    # Credential file management
│   ├── env_passthrough.py     # Environment variable passthrough to tools
│   ├── patch_parser.py        # Unified diff patch parsing
│   ├── fuzzy_match.py         # Fuzzy string matching utilities
│   ├── ansi_strip.py          # ANSI escape code stripping
│   ├── debug_helpers.py       # Debug utilities
│   ├── url_safety.py          # URL safety checking
│   ├── website_policy.py      # Website policy enforcement
│   ├── rl_training_tool.py    # RL training data tools
│   ├── neutts_synth.py        # Neural TTS synthesis
│   └── environments/          # Tool execution environment backends
│
├── hermes_cli/                # CLI command implementations and support
│   ├── main.py                # CLI entry point / argument dispatcher
│   ├── config.py              # YAML config management
│   ├── auth.py                # Multi-provider authentication
│   ├── runtime_provider.py    # Provider credential resolution
│   ├── env_loader.py          # .env file loading
│   ├── profiles.py            # Profile (isolated HERMES_HOME) management
│   ├── gateway.py             # Gateway service management commands
│   ├── cron.py                # Cron job management commands
│   ├── plugins.py             # Optional skills plugin system
│   ├── plugins_cmd.py         # Plugin CLI commands
│   ├── doctor.py              # Dependency checker
│   ├── setup.py               # Interactive setup wizard
│   ├── commands.py            # Shared command helpers
│   ├── models.py              # Model listing and management
│   ├── model_switch.py        # Model switching helpers
│   ├── mcp_config.py          # MCP configuration management
│   ├── skills_config.py       # Skills configuration helpers
│   ├── skills_hub.py          # Skills Hub CLI commands
│   ├── tools_config.py        # Per-platform toolset config
│   ├── status.py              # Status display
│   ├── banner.py              # ASCII art banner
│   ├── colors.py              # Terminal color helpers
│   ├── skin_engine.py         # Theme/skin engine
│   ├── curses_ui.py           # Curses-based UI components
│   ├── callbacks.py           # CLI callback implementations
│   ├── checklist.py           # Setup checklist display
│   ├── clipboard.py           # Clipboard integration
│   ├── claw.py                # OpenClaw migration helpers
│   ├── codex_models.py        # Codex/OpenAI model definitions
│   ├── copilot_auth.py        # GitHub Copilot authentication
│   ├── default_soul.py        # Default SOUL.md content
│   ├── pairing.py             # CLI pairing helpers
│   ├── uninstall.py           # Uninstall logic
│   └── webhook.py             # Webhook management
│
├── acp_adapter/               # ACP (Agent Communication Protocol) server
│   ├── entry.py               # CLI entry point
│   ├── server.py              # ACP JSON-RPC server
│   ├── session.py             # ACP session management
│   ├── tools.py               # ACP tool exposure
│   ├── events.py              # ACP event handling
│   └── permissions.py         # ACP permissions
│
├── acp_registry/              # ACP agent registration
│   ├── agent.json             # Agent descriptor
│   └── icon.svg               # Agent icon
│
├── cron/                      # Cron job scheduler
│   ├── scheduler.py           # APScheduler-based scheduler
│   ├── jobs.py                # Job definitions and storage
│   └── __init__.py
│
├── honcho_integration/        # Honcho AI memory integration
│
├── skills/                    # Bundled skills (organized by category)
│   ├── apple/                 # Apple platform skills
│   ├── creative/              # Creative skills
│   ├── data-science/          # Data science skills
│   ├── devops/                # DevOps skills
│   ├── github/                # GitHub skills
│   ├── research/              # Research skills
│   ├── software-development/  # Software development skills
│   └── ...                    # (30+ categories)
│
├── optional-skills/           # Optional skills requiring extra setup
│   ├── blockchain/            # Blockchain skills
│   ├── mcp/                   # MCP server skills
│   ├── security/              # Security skills
│   └── ...
│
├── tests/                     # Test suite
│   ├── agent/                 # Agent loop tests
│   ├── gateway/               # Gateway tests
│   ├── hermes_cli/            # CLI tests
│   ├── cron/                  # Cron scheduler tests
│   ├── acp/                   # ACP adapter tests
│   ├── honcho_integration/    # Honcho integration tests
│   ├── skills/                # Skills system tests
│   ├── integration/           # Integration tests
│   ├── fakes/                 # Test doubles/fakes
│   └── conftest.py            # Shared fixtures
│
├── environments/              # RL benchmark and test environments
│   ├── benchmarks/            # Benchmark suites (tblite, terminalbench, yc_bench)
│   ├── hermes_swe_env/        # SWE-bench environment
│   ├── terminal_test_env/     # Terminal tool test environment
│   └── tool_call_parsers/     # Tool call parsing utilities
│
├── docs/                      # Documentation
│   ├── migration/             # Migration guides
│   ├── plans/                 # Historical design plans
│   └── skins/                 # Theme documentation
│
├── docker/                    # Docker compose and related configs
├── nix/                       # Nix derivations and overlays
├── scripts/                   # Install and utility scripts
│   ├── install.sh
│   ├── install.ps1
│   ├── install.cmd
│   ├── hermes-gateway         # Gateway service helper
│   └── whatsapp-bridge        # WhatsApp bridge helper
├── assets/                    # Static assets (images, icons)
├── landingpage/               # Landing page source
├── website/                   # Website source
├── datagen-config-examples/   # Data generation config examples
├── tinker-atropos/            # Experimental/research code
└── plans/                     # Project planning documents
```

## Directory Purposes

**`agent/`:**
- Purpose: Support modules for the `AIAgent` class, extracted for modularity
- Contains: Stateless helpers for prompt building, context compression, model metadata, display, pricing, trajectory saving
- Key files: `prompt_builder.py`, `context_compressor.py`, `anthropic_adapter.py`, `display.py`

**`gateway/`:**
- Purpose: All messaging platform integration code
- Contains: Platform adapters, session management, delivery routing, event hooks
- Key files: `run.py` (GatewayRunner), `platforms/base.py` (BasePlatformAdapter), `session.py`, `config.py`

**`tools/`:**
- Purpose: Individual tool implementations, each self-registering into `ToolRegistry`
- Contains: 40+ tool modules covering terminal, file, web, browser, vision, memory, delegation, MCP, etc.
- Key files: `registry.py`, `terminal_tool.py`, `delegate_tool.py`, `skills_tool.py`

**`hermes_cli/`:**
- Purpose: All CLI subcommand implementations and shared CLI support utilities
- Contains: Command handlers, config management, auth, profile management, setup wizard
- Key files: `main.py` (dispatcher), `config.py`, `auth.py`, `runtime_provider.py`, `profiles.py`

**`skills/`:**
- Purpose: Bundled skill prompt bundles organized by domain category
- Contains: Directories named by category; each skill is a subdirectory with `SKILL.md`
- Key files: Each `SKILL.md` has YAML frontmatter (name, description, version, prerequisites, platforms) + markdown instructions

**`tests/`:**
- Purpose: Full test suite, mirroring the source tree structure
- Contains: Unit tests per module, integration tests, fakes/doubles
- Key files: `conftest.py`, `fakes/` (test doubles for LLM responses)

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `context_compressor.py`, `runtime_provider.py`)
- Tool files: `<tool_category>_tool.py` for single-tool files (e.g., `terminal_tool.py`, `clarify_tool.py`), or `<category>_tools.py` for multi-tool files (e.g., `file_tools.py`, `vision_tools.py`)
- Skill files: `SKILL.md` (always uppercase)
- Config files: `config.yaml`, `SOUL.md`, `MEMORY.md` (uppercase markdown docs)

**Directories:**
- Skills categories: `kebab-case` (e.g., `software-development`, `data-science`)
- Python packages: `snake_case` (e.g., `hermes_cli`, `acp_adapter`)
- Platform adapters: `<platform>.py` in `gateway/platforms/`

**Classes:**
- Major classes: `PascalCase` (e.g., `AIAgent`, `GatewayRunner`, `ToolRegistry`, `BasePlatformAdapter`)
- Data classes: `PascalCase` (e.g., `SessionSource`, `DeliveryTarget`, `HomeChannel`)

**Functions:**
- Public API: `snake_case` (e.g., `run_conversation`, `handle_function_call`, `build_session_key`)
- Private helpers: `_snake_case` with leading underscore (e.g., `_build_system_prompt`, `_run_agent`)

## Where to Add New Code

**New Tool:**
- Implementation: `tools/<name>_tool.py` (single tool) or `tools/<category>_tools.py` (multiple)
- Register with: `registry.register(name="...", toolset="...", schema={...}, handler=fn)` at module level
- Add to toolsets: `toolsets.py` in the appropriate `TOOLSETS` dict entry
- Add to core tools: `toolsets.py` `_HERMES_CORE_TOOLS` list if it should be on by default
- Import in: `model_tools.py` to trigger registration at discovery time

**New Platform Adapter:**
- Implementation: `gateway/platforms/<platform>.py`
- Inherit from: `gateway.platforms.base.BasePlatformAdapter`
- Register in: `gateway/run.GatewayRunner` adapter initialization
- Add to: `gateway/config.Platform` enum
- Follow: `gateway/platforms/ADDING_A_PLATFORM.md`

**New CLI Subcommand:**
- Implementation: `hermes_cli/<command>.py`
- Register in: `hermes_cli/main.py` argument parser dispatch

**New Agent Support Helper:**
- Implementation: `agent/<module>.py` (stateless helpers preferred)
- Import in: `run_agent.py` or wherever needed

**New Skill:**
- Create directory: `skills/<category>/<skill-name>/`
- Add: `SKILL.md` with YAML frontmatter (`name`, `description` required)
- Optional: `references/`, `templates/`, `assets/` subdirectories

**New Test:**
- Mirror source path: `tests/<same structure as source>/test_<module>.py`
- Use existing fakes: `tests/fakes/` for LLM response mocking

**Configuration additions:**
- User-facing settings: `~/.hermes/config.yaml` (document in `hermes_cli/config.py`)
- Secrets/API keys: `~/.hermes/.env` (document in `hermes_cli/config._EXTRA_ENV_KEYS`)

## Special Directories

**`~/.hermes/` (HERMES_HOME — not in repo):**
- Purpose: User data directory created at install time
- Generated: Yes, by `hermes setup`
- Committed: No
- Contains: `config.yaml`, `.env`, `state.db`, `sessions/`, `skills/`, `memories/`, `MEMORY.md`, `SOUL.md`, `hooks/`, `logs/`, `profiles/`, `cache/`

**`~/.hermes/profiles/<name>/` (not in repo):**
- Purpose: Isolated HERMES_HOME for each profile (independent config, sessions, skills, memory)
- Generated: Yes, by `hermes profile create`
- Committed: No

**`skills/index-cache/`:**
- Purpose: Cached skill metadata index for fast skills_list responses
- Generated: Yes, by skill scanning
- Committed: Yes (pre-built index for bundled skills)

**`.planning/` (in repo):**
- Purpose: GSD planning documents for this codebase
- Generated: By GSD map-codebase/plan-phase commands
- Committed: Yes

**`docs/plans/`:**
- Purpose: Historical design plans and architecture documents
- Generated: No
- Committed: Yes

---

*Structure analysis: 2026-03-30*
