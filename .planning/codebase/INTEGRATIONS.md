# External Integrations

**Analysis Date:** 2026-03-30

## LLM / AI Inference Providers

All providers are accessed via the OpenAI Python SDK with `base_url` overriding, except Anthropic which uses its native SDK.

**OpenRouter (primary default):**
- Purpose: Multi-provider LLM routing (Claude, GPT, Gemini, open models)
- Base URL: `https://openrouter.ai/api/v1`
- Auth: `OPENROUTER_API_KEY`
- Client: `openai.OpenAI(base_url=..., api_key=...)`
- Attribution headers: `HTTP-Referer`, `X-OpenRouter-Title`, `X-OpenRouter-Categories`
- Configuration: `cli-config.yaml` `model.base_url`, `provider_routing` section

**Nous Portal (first-party):**
- Purpose: Nous Research inference endpoint; primary alternative to OpenRouter
- Base URL: `https://inference-api.nousresearch.com/v1`
- Auth: `NOUS_API_KEY` or `~/.hermes/auth.json` (OAuth token from `hermes login`)
- Attribution: `extra_body: {"tags": ["product=hermes-agent"]}`
- Files: `hermes_constants.py`, `agent/auxiliary_client.py`

**Anthropic (native SDK):**
- Purpose: Native Claude access supporting OAuth tokens and beta features (extended thinking, prompt caching)
- Auth: `sk-ant-api*` keys (x-api-key header), `sk-ant-oat*` OAuth tokens (Bearer), or Claude Code credentials (`~/.claude.json`)
- Files: `agent/anthropic_adapter.py`

**OpenRouter AI Gateway:**
- Base URL: `https://ai-gateway.vercel.sh/v1`
- Files: `hermes_constants.py` (`AI_GATEWAY_BASE_URL`)

**Other direct API-key providers (OpenAI-compatible endpoints):**

| Provider | Env Var | Default Base URL | Files |
|----------|---------|-----------------|-------|
| z.ai / ZhipuAI GLM | `GLM_API_KEY` | `https://api.z.ai/api/paas/v4` | `agent/auxiliary_client.py` |
| Kimi / Moonshot AI | `KIMI_API_KEY` | `https://api.kimi.com/coding/v1` | `agent/auxiliary_client.py` |
| MiniMax (global) | `MINIMAX_API_KEY` | `https://api.minimax.io/v1` | `agent/auxiliary_client.py` |
| MiniMax (China) | `MINIMAX_CN_API_KEY` | `https://api.minimaxi.com/v1` | `agent/auxiliary_client.py` |
| OpenCode Zen | `OPENCODE_ZEN_API_KEY` | `https://opencode.ai/zen/v1` | `agent/auxiliary_client.py` |
| OpenCode Go | `OPENCODE_GO_API_KEY` | `https://opencode.ai/zen/go/v1` | `agent/auxiliary_client.py` |
| Hugging Face | `HF_TOKEN` | HF inference endpoint | `agent/auxiliary_client.py` |
| Codex OAuth | Browser OAuth | `chatgpt.com` responses API | `agent/auxiliary_client.py` |
| Custom endpoint | `OPENAI_BASE_URL` + `OPENAI_API_KEY` | User-defined | `agent/auxiliary_client.py` |

## Web Search and Content Extraction

**Firecrawl:**
- Purpose: Web search, content extraction, site crawling
- SDK: `firecrawl-py`
- Auth: `FIRECRAWL_API_KEY`
- Files: `tools/web_tools.py`

**Exa:**
- Purpose: AI-native semantic web search
- SDK: `exa-py`
- Auth: `EXA_API_KEY`
- Files: `tools/web_tools.py`

**Parallel:**
- Purpose: Web search and extract
- SDK: `parallel-web`
- Auth: `PARALLEL_API_KEY`
- Files: `tools/web_tools.py`

**Tavily:**
- Purpose: Web search (supported backend, no dedicated SDK)
- Auth: `TAVILY_API_KEY`
- Files: `tools/web_tools.py`

Backend selection: configured via `web.backend` in `~/.hermes/config.yaml` or auto-detected from available API keys.

## Image Generation

**FAL.ai (FLUX 2 Pro):**
- Purpose: Image generation with automatic 2x upscaling (Clarity Upscaler)
- SDK: `fal-client`
- Auth: `FAL_KEY`
- Default model: `fal-ai/flux-2-pro`
- Files: `tools/image_generation_tool.py`

## Browser Automation

**Browserbase (cloud mode):**
- Purpose: Cloud-hosted headless Chromium with stealth, proxies, CAPTCHA solving
- Auth: `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID`
- Env vars: `BROWSERBASE_PROXIES`, `BROWSERBASE_ADVANCED_STEALTH`, `BROWSERBASE_KEEP_ALIVE`, `BROWSERBASE_SESSION_TIMEOUT`
- Files: `tools/browser_tool.py`, `tools/browser_providers/browserbase.py`

**Local Chromium (default mode):**
- Purpose: Zero-cost local headless browser via `agent-browser` npm package
- CLI: `npx agent-browser` / `agent-browser install`
- Files: `tools/browser_tool.py`, `tools/browser_providers/browser_use.py`

## Text-to-Speech

**Edge TTS (default, free):**
- Purpose: Microsoft Edge neural voices, no API key required
- SDK: `edge-tts`
- Files: `tools/tts_tool.py`

**ElevenLabs (premium):**
- Purpose: High-quality voice synthesis
- SDK: `elevenlabs`
- Auth: `ELEVENLABS_API_KEY`
- Files: `tools/tts_tool.py`

**OpenAI TTS:**
- Purpose: OpenAI voice synthesis
- Auth: `VOICE_TOOLS_OPENAI_KEY` (separate from main OpenAI key to avoid conflicts)
- Files: `tools/tts_tool.py`

**NeuTTS (local):**
- Purpose: On-device TTS via `neutts_cli` binary
- Files: `tools/tts_tool.py`, `tools/neutts_synth.py`

## Speech-to-Text (STT)

**faster-whisper (local, default):**
- Purpose: Local on-device Whisper transcription
- SDK: `faster-whisper`
- Files: `tools/transcription_tools.py`

**OpenAI Whisper (cloud):**
- Purpose: Cloud Whisper API
- Auth: `VOICE_TOOLS_OPENAI_KEY`
- Default model: `whisper-1`
- Files: `tools/transcription_tools.py`

**Groq STT:**
- Purpose: Cloud Whisper via Groq API (fast inference)
- Auth: `GROQ_API_KEY`
- Default model: `whisper-large-v3-turbo`
- Files: `tools/transcription_tools.py`

## Messaging Platform Integrations (Gateway)

All adapters live in `gateway/platforms/`. Install via `pip install -e ".[messaging]"`.

**Telegram:**
- SDK: `python-telegram-bot` 22.6+
- Auth: `TELEGRAM_TOKEN` (bot token from BotFather)
- Access control: `TELEGRAM_ALLOWED_USERS`
- Files: `gateway/platforms/telegram.py`

**Discord:**
- SDK: `discord.py[voice]` 2.7.1+
- Auth: `DISCORD_BOT_TOKEN`
- Access control: `DISCORD_ALLOWED_USERS`
- Files: `gateway/platforms/discord.py`

**Slack:**
- SDK: `slack-bolt` 1.18.0+, `slack-sdk` 3.27.0+
- Auth: `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` (Socket Mode)
- Access control: `SLACK_ALLOWED_USERS`
- Files: `gateway/platforms/slack.py`

**WhatsApp:**
- Backend: Baileys (Node.js bridge subprocess) for personal accounts or WhatsApp Business API
- Bridge: `scripts/whatsapp-bridge/` (Node.js)
- Env vars: `WHATSAPP_ENABLED`, `WHATSAPP_ALLOWED_USERS`
- Files: `gateway/platforms/whatsapp.py`

**Matrix/Element:**
- SDK: `matrix-nio[e2e]` 0.24.0+ (optional E2EE)
- Auth: `MATRIX_ACCESS_TOKEN` or `MATRIX_PASSWORD`
- Env vars: `MATRIX_HOMESERVER`, `MATRIX_USER_ID`, `MATRIX_ENCRYPTION`, `MATRIX_ALLOWED_USERS`
- Files: `gateway/platforms/matrix.py`

**SMS (Twilio):**
- Purpose: SMS via Twilio REST API + inbound aiohttp webhook
- Auth: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- Webhook port: `SMS_WEBHOOK_PORT` (default 8080)
- Files: `gateway/platforms/sms.py`

**Signal:**
- Backend: `signal-cli` daemon running in HTTP mode (SSE inbound, JSON-RPC outbound)
- Env vars: `SIGNAL_HTTP_URL`, `SIGNAL_ACCOUNT`
- Files: `gateway/platforms/signal.py`

**Email (IMAP/SMTP):**
- Purpose: Receive/send emails as the agent
- Auth: `EMAIL_ADDRESS`, `EMAIL_PASSWORD` (app password for Gmail)
- Env vars: `EMAIL_IMAP_HOST`, `EMAIL_IMAP_PORT`, `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`, `EMAIL_POLL_INTERVAL`
- Files: `gateway/platforms/email.py`

**Mattermost:**
- Purpose: Self-hosted Mattermost via REST API v4 + WebSocket
- Auth: `MATTERMOST_TOKEN`
- Env vars: `MATTERMOST_URL`, `MATTERMOST_ALLOWED_USERS`
- Files: `gateway/platforms/mattermost.py`

**Home Assistant:**
- Purpose: Home Assistant smart home integration
- Optional extra: `[homeassistant]`
- Files: `gateway/platforms/homeassistant.py`, `tools/homeassistant_tool.py`

**DingTalk:**
- SDK: `dingtalk-stream` 0.1.0+
- Optional extra: `[dingtalk]`
- Files: `gateway/platforms/dingtalk.py`

**Webhook (generic):**
- Purpose: Generic HTTP webhook receiver for custom integrations
- Files: `gateway/platforms/webhook.py`

**API Server:**
- Purpose: REST API for programmatic agent interaction
- Files: `gateway/platforms/api_server.py`

## Cloud Execution Backends (Terminal Tool)

**Modal:**
- Purpose: Cloud GPU/CPU sandbox execution
- Auth: Modal CLI (`modal setup`) — no API key in `.env`
- Env var: `TERMINAL_MODAL_IMAGE` (container image)
- Optional extra: `[modal]`

**Daytona:**
- Purpose: Cloud dev environment sandboxes
- Auth: `DAYTONA_API_KEY`
- Optional extra: `[daytona]`

## Skills Hub / GitHub

**GitHub API:**
- Purpose: Search and install skills from GitHub repositories
- Auth: `GITHUB_TOKEN` (PAT, optional — for higher rate limits)
- GitHub App: `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY_PATH`, `GITHUB_APP_INSTALLATION_ID` (for bot identity)
- SDK: `PyJWT[crypto]` for App JWT auth; direct `httpx` for REST calls
- Files: `tools/skills_hub.py`, `tools/skills_guard.py`

## Cross-Session Memory

**Honcho:**
- Purpose: AI-native persistent user modeling across sessions and tools
- SDK: `honcho-ai` 2.0.1+
- Auth: `HONCHO_API_KEY`
- Config: `~/.honcho/config.json` (shared with Claude Code, Cursor)
- Files: `tools/honcho_tools.py`, `honcho_integration/`

## RL Training

**Tinker (Thinking Machines Lab):**
- Purpose: RL training framework
- SDK: `tinker` (git dependency)
- Auth: `TINKER_API_KEY`
- Files: `tools/rl_training_tool.py`, `environments/`

**Atropos (Nous Research):**
- Purpose: RL environment runner
- SDK: `atroposlib` (git dependency from NousResearch/atropos)
- Files: `environments/agent_loop.py`

**Weights & Biases:**
- Purpose: Experiment tracking and metrics for RL training
- SDK: `wandb`
- Auth: `WANDB_API_KEY`

## Security Scanning

**Tirith:**
- Purpose: Pre-execution command security scanning (homograph URLs, pipe-to-shell, terminal injection)
- Binary: `tirith` (external CLI tool, Homebrew: `sheeki03/tap/tirith`)
- Config: `security.tirith_enabled` in `~/.hermes/config.yaml`
- Files: `tools/tirith_security.py`

## MCP (Model Context Protocol)

- Purpose: Connect to external MCP servers to add arbitrary tools
- SDK: `mcp` 1.2.0+ (optional extra `[mcp]`)
- Transport: stdio (subprocess) or HTTP/StreamableHTTP
- Config: `mcp_servers:` section in `~/.hermes/config.yaml`
- Files: `tools/mcp_tool.py`

## ACP (Agent Client Protocol)

- Purpose: Interoperability with other ACP-compatible agent systems
- SDK: `agent-client-protocol` 0.8.1+
- Entry: `hermes-acp` CLI, `acp_adapter/entry.py`

## Webhooks & Callbacks

**Incoming:**
- SMS/Twilio: aiohttp HTTP server on `SMS_WEBHOOK_PORT` (default 8080)
- Signal: SSE streaming from `signal-cli` daemon HTTP endpoint
- Generic webhook: `gateway/platforms/webhook.py`

**Outgoing:**
- All messaging platforms send outbound via their respective SDKs/REST APIs

## Environment Configuration

**Required for basic operation:**
- At least one LLM provider key: `OPENROUTER_API_KEY` or `NOUS_API_KEY` or direct provider keys

**Required per feature:**
- Web search: `FIRECRAWL_API_KEY` or `EXA_API_KEY` or `PARALLEL_API_KEY` or `TAVILY_API_KEY`
- Image generation: `FAL_KEY`
- Browser (cloud): `BROWSERBASE_API_KEY` + `BROWSERBASE_PROJECT_ID`
- Voice transcription: `VOICE_TOOLS_OPENAI_KEY` or `GROQ_API_KEY` (or none for local)
- Premium TTS: `ELEVENLABS_API_KEY`
- Telegram: `TELEGRAM_TOKEN`
- Discord: `DISCORD_BOT_TOKEN`
- Slack: `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN`
- SMS: `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` + `TWILIO_PHONE_NUMBER`
- RL training: `TINKER_API_KEY`
- Memory: `HONCHO_API_KEY` (optional, file-based memory works without it)

**Secrets location:**
- `~/.hermes/.env` (loaded at startup via `python-dotenv`)
- `~/.hermes/auth.json` (OAuth tokens from `hermes login`)
- `~/.honcho/config.json` (Honcho credentials)
- `~/.claude.json` or `~/.claude/.credentials.json` (Claude Code tokens)

---

*Integration audit: 2026-03-30*
