# Technology Stack

**Analysis Date:** 2026-03-30

## Languages

**Primary:**
- Python 3.11+ - Core agent logic, all tools, gateway, CLI, RL environments
- JavaScript/Node.js 18+ - Browser automation runner (`agent-browser` npm package), WhatsApp bridge scripts

**Secondary:**
- Nix (Flake) - Reproducible dev environments and NixOS module packaging

## Runtime

**Environment:**
- CPython ≥ 3.11 (required by `pyproject.toml`)
- Node.js ≥ 18.0.0 (required by `package.json` engines field)

**Package Manager:**
- Python: `uv` (preferred) — lockfile at `uv.lock`; also `pip`-compatible via `pyproject.toml`
- Node.js: `npm` — lockfile at `package-lock.json`
- Nix: `flake.lock` for reproducible system environments

## Frameworks

**Core:**
- No web framework for main agent loop (pure asyncio + threads)
- `prompt_toolkit` 3.0.52+ - Interactive CLI REPL (`cli.py`, `hermes_cli/`)
- `rich` 14.3.3+ - Terminal rendering, panels, progress, syntax highlighting
- `pydantic` 2.12.5+ - Data validation and typed config models
- `jinja2` 3.1.5+ - Prompt/template rendering
- `fire` 0.7.1+ - CLI entrypoint argument parsing (`run_agent.py`, `rl_cli.py`)
- `tenacity` 9.1.4+ - Retry logic for LLM API calls

**Gateway (messaging platform server):**
- `aiohttp` 3.13.3+ - HTTP server/client for webhooks (SMS, Mattermost, Home Assistant, Signal)
- `asyncio` (stdlib) - Async event loop for all platform adapters

**RL / Training:**
- `fastapi` 0.104.0+ - REST API server for RL environment (`rl` optional extra)
- `uvicorn[standard]` 0.24.0+ - ASGI server for FastAPI RL endpoint

**Testing:**
- `pytest` 9.0.2+ - Test runner
- `pytest-asyncio` 1.3.0+ - Async test support
- `pytest-xdist` 3.0+ - Parallel test execution (`-n auto`)

**Build/Dev:**
- `setuptools` ≥ 61.0 - Build backend for `pyproject.toml`
- `uv` - Fast virtual environment + lockfile management
- Nix flake with `uv2nix` + `pyproject-nix` - NixOS packaging

## Key Dependencies

**Critical:**
- `openai` 2.21.0–3 - Primary LLM client; all providers use OpenAI-compatible API via base_url override
- `anthropic` 0.39.0–1 - Native Anthropic SDK (`agent/anthropic_adapter.py`); required for Claude OAuth tokens and native beta features
- `httpx` 0.28.1+ - Async HTTP client for direct API calls and tool backends
- `python-dotenv` 1.2.1+ - Loads `~/.hermes/.env` at startup
- `pyyaml` 6.0.2+ - Reads `~/.hermes/config.yaml`

**Tool backends:**
- `firecrawl-py` 4.16.0+ - Web search, extract, crawl (`tools/web_tools.py`)
- `exa-py` 2.9.0+ - AI-native web search (`tools/web_tools.py`)
- `parallel-web` 0.4.2+ - Parallel web search/extract (`tools/web_tools.py`)
- `fal-client` 0.13.1+ - Image generation via FAL.ai FLUX models (`tools/image_generation_tool.py`)
- `edge-tts` 7.2.7+ - Free Microsoft Edge TTS (`tools/tts_tool.py`)
- `faster-whisper` 1.0.0+ - Local speech-to-text (`tools/transcription_tools.py`)
- `PyJWT[crypto]` 2.12.0+ - GitHub App JWT auth for Skills Hub (`tools/skills_hub.py`)
- `agent-browser` 0.13.0 (npm) - Headless Chromium browser control (`tools/browser_tool.py`)

**Optional extras (installed via `pip install -e ".[extra]"`):**
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

**Environment:**
- Primary config: `~/.hermes/config.yaml` (YAML, mirrors `cli-config.yaml.example`)
- Secrets/keys: `~/.hermes/.env` (dotenv format, never committed)
- Home dir: `HERMES_HOME` env var (default `~/.hermes`), resolved by `hermes_constants.get_hermes_home()`
- Config structure: model provider, terminal backend, memory, compression, toolsets per platform, streaming, session reset, display/skin, MCP servers

**Build:**
- `pyproject.toml` - canonical dependency list and entry points
- `package.json` - Node.js browser tooling only
- `Dockerfile` - Debian 13.4 base with Python 3, Node.js, ffmpeg, Chromium (playwright)
- `Dockerfile.enclava` - Enclava platform variant
- `flake.nix` - Nix packaging for x86_64-linux, aarch64-linux, aarch64-darwin

## Platform Requirements

**Development:**
- Python ≥ 3.11
- Node.js ≥ 18 (for browser tools)
- `ffmpeg` (for audio format conversion in TTS)
- `ripgrep` (for file search tools)
- Optional: Nix with flakes enabled

**Production:**
- Runs anywhere Python ≥ 3.11 is available: local machine, SSH server, Docker, Modal cloud, Daytona cloud, Singularity/HPC
- Docker: `debian:13.4` with all deps via `docker/entrypoint.sh`
- NixOS: `flake.nix` provides a NixOS module
- Enclava: specialized container via `Dockerfile.enclava`
- Data volume: `/opt/data` (Docker) or `~/.hermes` (local)

---

*Stack analysis: 2026-03-30*
