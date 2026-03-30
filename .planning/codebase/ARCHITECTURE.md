# Architecture

**Analysis Date:** 2026-03-30

## Pattern Overview

**Overall:** Multi-surface AI agent platform with a shared core agent loop, platform-agnostic gateway layer, and plugin-style tool/skill system.

**Key Characteristics:**
- `AIAgent` (in `run_agent.py`) is the central agent class used by all surfaces (CLI, gateway, cron, ACP, batch runner)
- Platform adapters (messaging platforms) are isolated in `gateway/platforms/` behind a common `BasePlatformAdapter` ABC
- Tools self-register into a singleton `ToolRegistry` at import time — no central registration list
- Skills are file-system-based prompt bundles loaded dynamically at runtime
- All persistent state lives in `~/.hermes/` (SQLite for sessions, YAML for config, markdown for memory/skills)

## Layers

**Entry Points (CLI / ACP / Batch):**
- Purpose: Accept user input and invoke AIAgent
- Location: `cli.py`, `hermes_cli/main.py`, `run_agent.py`, `acp_adapter/entry.py`, `batch_runner.py`, `rl_cli.py`
- Contains: Argument parsing, TUI/REPL, lifecycle management, profile bootstrapping
- Depends on: `agent/`, `model_tools.py`, `hermes_cli/`
- Used by: End users, CI pipelines, RL training harnesses

**Gateway Layer:**
- Purpose: Bridge messaging platforms (Telegram, Discord, Slack, etc.) to the agent core
- Location: `gateway/`
- Contains: `GatewayRunner` (orchestrator), platform adapters, session management, delivery routing, event hooks, cron scheduler integration
- Depends on: `run_agent.AIAgent`, `gateway/platforms/`, `gateway/session.py`, `gateway/delivery.py`, `gateway/hooks.py`
- Used by: `hermes_cli/gateway.py`, `hermes gateway start`

**Platform Adapters:**
- Purpose: Normalize inbound messages from each platform into `MessageEvent`, send formatted responses back
- Location: `gateway/platforms/` (`telegram.py`, `discord.py`, `slack.py`, `whatsapp.py`, `signal.py`, `matrix.py`, `mattermost.py`, `email.py`, `sms.py`, `dingtalk.py`, `api_server.py`, `webhook.py`, `homeassistant.py`)
- Contains: Bot clients, message parsing, image caching, token/session locking
- Depends on: `gateway/platforms/base.py` (`BasePlatformAdapter`), `gateway/session.py`, `gateway/config.py`
- Used by: `gateway/run.GatewayRunner`

**Agent Core:**
- Purpose: Manage the tool-calling conversation loop, system prompt assembly, context compression, model routing
- Location: `run_agent.py` (`AIAgent` class, ~6000 lines), `agent/`
- Contains: Conversation loop, prompt building, model API calls, tool dispatch, context compression, trajectory saving, usage accounting, display helpers
- Depends on: `model_tools.py`, `agent/prompt_builder.py`, `agent/context_compressor.py`, `agent/anthropic_adapter.py`, `agent/model_metadata.py`, `hermes_state.py`
- Used by: `cli.py`, `gateway/run.py`, `cron/`, `acp_adapter/`, `batch_runner.py`

**Agent Support Package (`agent/`):**
- Purpose: Modular helpers extracted from the monolithic agent class
- Location: `agent/`
- Contains:
  - `prompt_builder.py` — Stateless system prompt assembly (identity, platform hints, skills index, context files)
  - `context_compressor.py` — Automatic context window compression via auxiliary LLM
  - `anthropic_adapter.py` — Anthropic Messages API translation layer (handles OpenAI-style internal format)
  - `model_metadata.py` — Model context length probing and token estimation
  - `smart_model_routing.py` — Optional cheap-vs-strong model routing based on task complexity
  - `usage_pricing.py` — Token cost estimation across providers
  - `display.py` — Tool progress messages, spinners, emoji mapping
  - `trajectory.py` — Trajectory/replay saving in ShareGPT format
  - `skill_commands.py` — Slash command handling shared between CLI and gateway
  - `auxiliary_client.py` — Lightweight LLM client for summarization and side tasks
  - `redact.py` — Secret redaction from tool outputs

**Tool System:**
- Purpose: Modular capabilities exposed to the LLM as function-call tools
- Location: `tools/`, `model_tools.py`, `toolsets.py`
- Contains: 40+ tool modules, a singleton `ToolRegistry`, toolset grouping definitions
- Pattern: Each `tools/*.py` calls `registry.register(name, toolset, schema, handler, ...)` at module import time; `model_tools.py` triggers discovery by importing all tool modules
- Depends on: `tools/registry.py`
- Used by: `run_agent.AIAgent` via `model_tools.handle_function_call()`

**Skills System:**
- Purpose: User-extensible prompt bundles that inject domain knowledge into the system prompt
- Location: `skills/` (bundled), `~/.hermes/skills/` (user), `tools/skills_tool.py`, `agent/skill_utils.py`
- Contains: Category directories, each skill as a directory with `SKILL.md` (YAML frontmatter + markdown instructions), optional `references/`, `templates/`, `assets/`
- Depends on: `agent/prompt_builder.build_skills_system_prompt()`
- Used by: `AIAgent._build_system_prompt()`, `tools/skill_manager_tool.py`

**Session & State:**
- Purpose: Persist conversation history, session metadata, and search index
- Location: `hermes_state.py` (`SessionDB`), `gateway/session.py` (`SessionStore`, `SessionContext`)
- Contains: SQLite with WAL mode, FTS5 full-text search, session chaining for compressed sessions
- Depends on: `hermes_constants.get_hermes_home()`
- Used by: `cli.py`, `gateway/run.GatewayRunner`, `tools/session_search_tool.py`

**CLI Support (`hermes_cli/`):**
- Purpose: CLI command implementations, configuration, auth, and setup
- Location: `hermes_cli/`
- Contains: `main.py` (entry point/argument dispatch), `config.py` (YAML config management), `auth.py` (multi-provider auth), `runtime_provider.py` (provider resolution), `profiles.py` (isolated HERMES_HOME profiles), `gateway.py` (gateway service management), `cron.py` (cron job management), `plugins.py`/`plugins_cmd.py` (optional skills management), `doctor.py` (dependency checker), `setup.py` (setup wizard), `skin_engine.py`, `banner.py`
- Depends on: `hermes_constants.py`, `hermes_state.py`
- Used by: `hermes_cli/main.py`, `cli.py`, `gateway/run.py`

**Cron Scheduler:**
- Purpose: Schedule recurring agent tasks with delivery routing
- Location: `cron/`
- Contains: `scheduler.py` (APScheduler-based), `jobs.py` (job definitions), `__init__.py`
- Depends on: `run_agent.AIAgent`, `gateway/delivery.py`
- Used by: `gateway/run.GatewayRunner`, `hermes cron` commands

**ACP Adapter:**
- Purpose: Expose Hermes as an Agent Communication Protocol (ACP) server for editor integration
- Location: `acp_adapter/`
- Contains: `entry.py` (CLI entry), `server.py` (ACP JSON-RPC server), `session.py`, `tools.py`, `events.py`, `permissions.py`
- Depends on: `run_agent.AIAgent`
- Used by: `hermes acp`, editor integrations

## Data Flow

**CLI Conversation Turn:**

1. User types message in `cli.py` REPL (prompt_toolkit TUI)
2. `cli.py` calls `agent.run_conversation(user_message, conversation_history=...)`
3. `AIAgent._build_system_prompt()` assembles prompt from identity + skills index + context files + memory
4. `AIAgent` sends message to model API (OpenAI-compat / Anthropic native / OpenRouter / local)
5. Model responds with text or tool calls
6. Tool calls dispatched via `model_tools.handle_function_call()` → `tools/registry.dispatch()` → individual tool handler
7. Tool result appended to message history, loop continues until no more tool calls
8. Final response returned to `cli.py` for display; session saved to `hermes_state.SessionDB`

**Gateway Message Turn:**

1. Platform adapter receives message, emits `MessageEvent` to `GatewayRunner`
2. `GatewayRunner` looks up or creates `SessionContext` (conversation history + session key)
3. `GatewayRunner._run_agent()` called in thread pool to avoid blocking event loop
4. Retrieves or creates cached `AIAgent` (per session key, preserving prompt cache)
5. `AIAgent.run_conversation()` executes same tool-calling loop as CLI
6. Tool progress callbacks stream intermediate status back to platform via `progress_queue`
7. Final response routed through `DeliveryRouter` to correct platform/channel
8. Session history saved to `SessionStore` (disk JSON) and `SessionDB` (SQLite)

**Subagent Delegation:**

1. Parent agent calls `delegate_task` tool
2. `tools/delegate_tool.py` spawns child `AIAgent` in `ThreadPoolExecutor` thread
3. Child gets isolated task_id (own terminal session), restricted toolset, focused system prompt
4. Blocked tools (`delegate_task`, `clarify`, `memory`, `send_message`, `execute_code`) are stripped
5. Child runs to completion; parent receives only the summary, not intermediate tool calls
6. Up to `MAX_CONCURRENT_CHILDREN=3` children may run in parallel; max depth is 2

**State Management:**
- Conversation history: in-memory list of OpenAI-format dicts, serialized to disk between turns (gateway) or kept in-process (CLI)
- Session database: `~/.hermes/state.db` (SQLite WAL, FTS5)
- Memory: `~/.hermes/MEMORY.md` (markdown, updated by `memory` tool)
- Config: `~/.hermes/config.yaml` (YAML, read at gateway startup and per agent run)
- Context compression: triggered automatically when approaching context limit; uses auxiliary cheap model to summarize middle turns; resulting summary prepended as synthetic message

## Key Abstractions

**`AIAgent` (run_agent.py:443):**
- Purpose: The universal agent class. All surfaces instantiate this to run conversations.
- Pattern: Stateful object (holds message history, session config), but `run_conversation()` is the external API. Callbacks (`tool_progress_callback`, `stream_delta_callback`, `step_callback`) decouple the display layer from the agent loop.

**`BasePlatformAdapter` (gateway/platforms/base.py):**
- Purpose: ABC for all messaging platform integrations
- Pattern: Subclasses implement `start()`, `stop()`, and async message handling. Platforms lock per-session tokens to serialize concurrent messages.

**`ToolRegistry` (tools/registry.py):**
- Purpose: Singleton collecting all tool schemas and handlers
- Pattern: Tool files call `registry.register()` at module import time. `model_tools.py` imports all tool modules to trigger registration, then queries the registry.

**`SessionContext` (gateway/session.py):**
- Purpose: Tracks where a message came from (`SessionSource`) and all conversation state for a given chat
- Pattern: Keyed by `(platform, chat_id, thread_id)` tuple; stored as JSONL files in `~/.hermes/sessions/`

**`DeliveryRouter` (gateway/delivery.py):**
- Purpose: Routes agent output to correct platform/channel
- Pattern: Parses target strings like `"telegram:123456"`, `"origin"`, `"local"` into `DeliveryTarget` dataclasses

**`HookRegistry` (gateway/hooks.py):**
- Purpose: Event-driven lifecycle hooks at `gateway:startup`, `session:start/end`, `agent:start/step/end`, `command:*`
- Pattern: Hook handlers are Python files discovered in `~/.hermes/hooks/` with a `HOOK.yaml` descriptor

**`IterationBudget` (run_agent.py:170):**
- Purpose: Thread-safe iteration counter with per-agent cap (parent: 90, subagent: 50)
- Pattern: Prevents runaway tool-calling loops; shared between parent and subagent when needed

## Entry Points

**Interactive CLI:**
- Location: `cli.py`, invoked as `hermes` or `hermes chat`
- Triggers: Direct user invocation
- Responsibilities: TUI REPL, command routing, session management, profile selection, tool display

**CLI Entry Dispatcher:**
- Location: `hermes_cli/main.py`
- Triggers: `hermes <subcommand>`
- Responsibilities: Routes `hermes gateway`, `hermes cron`, `hermes setup`, `hermes doctor`, `hermes sessions browse`, `hermes acp`, `hermes profile`, `hermes honcho`, etc.

**Gateway Runner:**
- Location: `gateway/run.py`, class `GatewayRunner`
- Triggers: `hermes gateway` or systemd service
- Responsibilities: Start all configured platform adapters, route messages to agent, manage session lifecycle, run cron scheduler

**ACP Server:**
- Location: `acp_adapter/entry.py`
- Triggers: `hermes acp` or `hermes-acp`
- Responsibilities: JSON-RPC stdio transport for editor integration (ACP protocol)

**Batch Runner:**
- Location: `batch_runner.py`
- Triggers: Direct invocation for RL/eval workloads
- Responsibilities: Run multiple agent conversations in parallel for training data generation

## Error Handling

**Strategy:** Fail-open with logging. Most subsystems catch exceptions, log them, and continue rather than crash the entire agent/gateway.

**Patterns:**
- Tool errors are returned as error strings to the model (not raised); model decides how to recover
- Gateway hooks catch all handler exceptions — hook failures never block message delivery
- Platform adapter connection failures are retried with exponential backoff in background
- Context overflow triggers automatic compression rather than hard failure
- `_SafeWriter` wraps stdout/stderr to absorb `OSError`/`ValueError` from broken pipes in headless/daemon mode
- `IterationBudget` caps runaway loops with a graceful stop message

## Cross-Cutting Concerns

**Logging:** Python stdlib `logging` module throughout; gateway uses `RotatingFileHandler` to `~/.hermes/logs/`; ACP adapter routes all logs to stderr to keep stdout clean for JSON-RPC transport

**Validation:** Tool schemas validated at registration time by `ToolRegistry`; platform config validated in `gateway/config.py` dataclasses; SKILL.md frontmatter parsed in `agent/skill_utils.py`

**Authentication:** Multi-provider auth resolved via `hermes_cli/auth.py` and `hermes_cli/runtime_provider.py`; API keys loaded from `~/.hermes/.env` at startup; Claude Code credentials supported natively in `agent/anthropic_adapter.py`

**Configuration:** Single source of truth is `~/.hermes/config.yaml`; env vars in `~/.hermes/.env`; profile isolation via `HERMES_HOME` override pointing to `~/.hermes/profiles/<name>/`

**Security:** Prompt injection scanning in `agent/prompt_builder._scan_context_content()`; secret redaction in `agent/redact.py`; Tirith security scanner integrated in gateway init; `tools/skills_guard.py` for skill execution safety

---

*Architecture analysis: 2026-03-30*
