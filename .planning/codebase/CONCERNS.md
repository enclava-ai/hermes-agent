# Codebase Concerns

**Analysis Date:** 2026-03-30

## Tech Debt

**God Files — Monolithic Core Modules:**
- Issue: Four files contain the bulk of application logic with no clear internal decomposition, making them hard to test, extend, and review safely.
- Files: `run_agent.py` (8,283 lines), `cli.py` (7,614 lines), `gateway/run.py` (5,931 lines), `hermes_cli/main.py` (4,804 lines)
- Impact: Changes anywhere in these files risk unintended side effects. `run_agent.py` alone has 112 try blocks. PRs touching these files have a high cognitive load.
- Fix approach: Extract logically cohesive units into submodules (as was started with `agent/`). `run_agent.py` should be split into the agent loop, streaming adapters, and provider-specific code.

**Pervasive Global State:**
- Issue: Multiple modules use module-level mutable globals accessed via `global` declarations: `_active_worktree` in `cli.py`, `auxiliary_is_nous` in `agent/auxiliary_client.py`, `_skill_commands` in `agent/skill_commands.py`, `_plugin_manager` in `hermes_cli/plugins.py`, `_tool_executor` in `environments/agent_loop.py`.
- Files: `cli.py`, `agent/auxiliary_client.py`, `agent/skill_commands.py`, `hermes_cli/plugins.py`, `environments/agent_loop.py`
- Impact: Global state makes multi-process/test isolation fragile. Tests can leak state between cases.
- Fix approach: Wrap shared state in context objects or singletons with explicit lifecycle management.

**Dependency on Unpinned Git Refs:**
- Issue: Three `[rl]` and `[yc-bench]` dependencies are installed directly from GitHub without version pinning (no tag or commit SHA), meaning `pip install` can silently pull in breaking changes.
- Files: `pyproject.toml` lines 62–68
  ```
  "atroposlib @ git+https://github.com/NousResearch/atropos.git"
  "tinker @ git+https://github.com/thinking-machines-lab/tinker.git"
  "yc-bench @ git+https://github.com/collinear-ai/yc-bench.git"
  ```
- Impact: Reproducible builds are not guaranteed for the RL and benchmark extras. CI could break at any time.
- Fix approach: Pin to a specific commit SHA or tag: `git+https://...@<sha>`.

**TODO: Nous Portal Transparent Proxy Not Yet Re-enabled:**
- Issue: OpenRouter provider preferences are explicitly disabled for Nous endpoints while waiting for Nous Portal backend support.
- Files: `run_agent.py` line 4740
- Impact: Users on Nous Portal cannot use provider preferences/routing.
- Fix approach: Re-enable once `_is_nous` check is updated per the TODO comment.

**ACP Non-Text Content Blocks Silently Dropped:**
- Issue: The ACP server ignores non-text content blocks (images, audio, resources) with only a comment noting this limitation.
- Files: `acp_adapter/server.py` line 77
- Impact: Multimodal ACP messages lose non-text content without any warning to callers.
- Fix approach: At minimum, return a structured warning; ideally, pass through image/audio blocks to the agent.

## Security Considerations

**Timing-Unsafe API Key Comparison in API Server:**
- Risk: The gateway API server compares Bearer tokens with `==` (non-constant-time string equality), which is vulnerable to timing attacks.
- Files: `gateway/platforms/api_server.py` line 366
  ```python
  if token == self._api_key:
  ```
- Current mitigation: None. Webhook validation uses `hmac.compare_digest` correctly, but the API server does not.
- Recommendations: Replace with `hmac.compare_digest(token, self._api_key)`.

**API Server Allows All Requests When No Key Is Configured:**
- Risk: If `API_SERVER_KEY` is not set, the API server accepts all requests without authentication. This is documented as intended for local use, but is a misconfiguration risk when accidentally exposed to a network.
- Files: `gateway/platforms/api_server.py` lines 360–361
- Current mitigation: CORS origin allowlisting provides partial protection.
- Recommendations: Log a startup warning when no key is set; consider requiring explicit opt-in for unauthenticated mode.

**`shell=True` in User-Facing Quick Commands:**
- Risk: Quick commands from `config.yaml` are executed with `shell=True`, meaning shell metacharacters in the command string are interpreted by the OS shell. The command string comes from user config, not from attacker-controlled input, but misconfiguration could be dangerous.
- Files: `cli.py` line 3862
- Current mitigation: Input comes from the user's own config file.
- Recommendations: Parse the quick command string as a list (via `shlex.split`) and remove `shell=True`.

**`shell=True` for Docker Container Cleanup:**
- Risk: `stop_cmd` and removal commands are built with f-strings containing `self._container_id` (sourced from `docker run` stdout) then passed to `shell=True`. While Docker IDs are hex strings, this is structurally unsafe.
- Files: `tools/environments/docker.py` lines 503, 511
- Current mitigation: Container IDs are validated implicitly as hex by Docker.
- Recommendations: Replace shell interpolation with a list of args passed to `subprocess.Popen` without `shell=True`.

**Tirith Security Scanner Defaults to Fail-Open:**
- Risk: The command-safety scanner (`tirith`) defaults to `tirith_fail_open: True`, meaning if tirith is unavailable, times out, or returns an unexpected exit code, commands are allowed through unchecked.
- Files: `tools/tirith_security.py` line 74, lines 630–651
- Current mitigation: Warnings are logged on fail-open.
- Recommendations: Document the fail-open default prominently; consider exposing a warning to the user when tirith is bypassed.

**Plugin Loading Executes Arbitrary Code Without Isolation:**
- Risk: Directory-based plugins are loaded via `importlib.util.exec_module()` with no sandbox or permission restriction. Any plugin can access the full Python environment and system.
- Files: `hermes_cli/plugins.py` lines 354–382
- Current mitigation: `skills_guard` scans community skills before install; there is no runtime sandbox.
- Recommendations: Document the trust model explicitly. Consider an allowlist of permitted plugin capabilities.

**Home Assistant Default URL Uses HTTP:**
- Risk: The default `HASS_URL` is `http://homeassistant.local:8123` (plaintext HTTP). Credentials sent to this URL are not encrypted in transit.
- Files: `gateway/platforms/homeassistant.py` line 78, `tools/homeassistant_tool.py` line 34, `hermes_cli/tools_config.py` line 281
- Current mitigation: Home Assistant is typically local-network only.
- Recommendations: Document the risk; suggest HTTPS when Home Assistant is exposed beyond LAN.

## Performance Bottlenecks

**`time.sleep()` in Async Context (Display/Animation):**
- Problem: `agent/display.py` uses `time.sleep()` inside animation loops (0.1–0.5s sleeps), which blocks the event loop thread when called from async contexts.
- Files: `agent/display.py` lines 300, 310, 319, 332
- Cause: Display animations are designed for blocking threads, not async event loops.
- Improvement path: Migrate animation loops to `asyncio.sleep()` or run them in a dedicated thread via `loop.run_in_executor`.

**Signal Platform Uses Infinite SSE Timeout:**
- Problem: The Signal gateway SSE connection is opened with `timeout=None`, meaning a stalled connection that never sends data will hang indefinitely.
- Files: `gateway/platforms/signal.py` line 298
- Cause: SSE streams are expected to be long-lived, but without a read timeout or activity deadline, a dead connection is not detected until reconnect logic triggers.
- Improvement path: Add a read timeout or a `_last_sse_activity` watchdog that forces reconnect if no data arrives within a configurable window.

**Stray `print()` Instead of Logging (4,100+ Calls):**
- Problem: Over 4,100 `print()` calls exist in production code outside of intentional CLI output. These bypass the logging framework, cannot be filtered by log level, and produce noise in structured deployments.
- Files: Distributed across `cli.py`, `gateway/run.py`, `hermes_cli/main.py`, and many tool files.
- Cause: Organic growth; no lint rule enforcing `logger.*` usage.
- Improvement path: Add a `no-print` ruff/pylint rule excluding intentional CLI output paths; progressively migrate to `logger.debug/info`.

**Model Metadata Cache Is Global and Module-Level:**
- Problem: `_model_metadata_cache` in `agent/model_metadata.py` is a plain dict with no size bound. In long-running gateway processes querying many unique endpoints, this grows without bound.
- Files: `agent/model_metadata.py` lines 62–66
- Cause: Simple TTL cache with no eviction.
- Improvement path: Replace with `functools.lru_cache` or a bounded dict with TTL eviction.

## Fragile Areas

**ACP Session Layer — Extensive Broad Exception Swallowing:**
- Files: `acp_adapter/session.py` (17 `except Exception: pass` or `except Exception: logger.*` blocks), `acp_adapter/server.py` (10 similar blocks)
- Why fragile: Silent `except Exception` blocks hide bugs and make debugging failures very hard. A broken persist or restore silently fails, leaving sessions in an inconsistent state.
- Safe modification: When touching ACP session code, add specific exception types and always log with `exc_info=True`. Do not add more bare `except Exception: pass` blocks.
- Test coverage: `tests/acp/test_session.py` covers the happy path; failure paths are largely untested.

**`auxiliary_client.py` — Global Flag for Provider Detection:**
- Files: `agent/auxiliary_client.py` lines 577, 742
- Why fragile: `auxiliary_is_nous` is a module-level global set at startup. Changing providers mid-session does not update this flag. Tests that import this module must reset state manually.
- Safe modification: Pass provider context as function arguments rather than reading the global.
- Test coverage: `tests/test_auxiliary_config_bridge.py` covers wiring but not provider-switching mid-session.

**Context Compressor Token Estimation Is Heuristic:**
- Files: `agent/context_compressor.py` lines 508–522
- Why fragile: Token counting uses a characters-per-token heuristic (`len(content) // _CHARS_PER_TOKEN + 10`) rather than actual tokenization. This can cause over- or under-compression, especially for code-heavy or multi-language conversations.
- Safe modification: Any changes to compression thresholds should be validated against a corpus. The test `tests/test_413_compression.py` covers the boundary condition.
- Test coverage: Covered for boundary cases; not validated against real token counts.

**Docker Container Cleanup Uses Fire-and-Forget Background Processes:**
- Files: `tools/environments/docker.py` lines 503, 511
- Why fragile: Container stop/remove is done via `subprocess.Popen(shell=True)` background processes. If the process fails, there is no notification, and the container leaks. On test teardown this can leave orphan containers.
- Safe modification: Wrap cleanup in a function that captures and logs `Popen` stderr; add a `docker ps -a` check in integration tests.
- Test coverage: Not unit tested; cleanup is exercised only in integration tests.

**Skill Code Execution Tempdir Not Always Cleaned Up:**
- Files: `tools/code_execution_tool.py` lines 388, 645
- Why fragile: `tmpdir` is created with `mkdtemp` and only cleaned up in the success path (`shutil.rmtree` at line 645). If an exception occurs between creation and cleanup, the temp directory leaks.
- Safe modification: Wrap in `try/finally` or use `tempfile.TemporaryDirectory()` as a context manager.
- Test coverage: Not tested for failure paths.

## Scaling Limits

**ACP `ThreadPoolExecutor` Fixed at 4 Workers:**
- Current capacity: `_executor = ThreadPoolExecutor(max_workers=4)` in `acp_adapter/server.py` line 58
- Limit: More than 4 concurrent ACP agent runs will queue. Under high load, this creates backpressure at the protocol layer.
- Scaling path: Make `max_workers` configurable via env var or config; evaluate moving to async-native agent invocation.

**Pairing Rate Limiting Stored in JSON File:**
- Current capacity: `_rate_limits.json` is read and written on every pairing request with no in-memory caching.
- Limit: Under concurrent pairing requests, this file becomes a serialization bottleneck and is not atomic across processes.
- Scaling path: Move to an in-memory cache with periodic persistence, or use SQLite with the existing session DB.

## Dependencies at Risk

**`agent-client-protocol>=0.8.1,<0.9` (ACP):**
- Risk: Pinned to a narrow pre-1.0 range. Pre-1.0 libraries frequently have breaking API changes.
- Impact: An ACP protocol update may require significant `acp_adapter/` rewrites.
- Migration plan: Track upstream releases; bump the constraint as each minor version is validated.

**`atroposlib`, `tinker` (RL extras):**
- Risk: Both are installed from the default branch of GitHub repos with no pin. Either repo's default branch can break the RL extra at any time.
- Impact: Breaks `hermes-agent[rl]` and all RL training workflows.
- Migration plan: Pin to a specific commit SHA in `pyproject.toml`.

## Test Coverage Gaps

**`tools/tirith_security.py` — Fail-Open Path:**
- What's not tested: The behavior when tirith is absent, times out, or returns an unexpected exit code in fail-open mode.
- Files: `tools/tirith_security.py` lines 627–651
- Risk: A broken tirith installation silently allows all commands through without any observable signal in tests.
- Priority: High

**`tools/environments/docker.py` — Error Paths:**
- What's not tested: Container start failure, cleanup failure, and stop timeout behavior.
- Files: `tools/environments/docker.py`
- Risk: Orphaned containers in CI, silent resource leaks in production.
- Priority: Medium

**`acp_adapter/session.py` — Persist/Restore Failure Paths:**
- What's not tested: Database write failures, session restore from corrupt state, concurrent session access.
- Files: `acp_adapter/session.py`
- Risk: Data loss or inconsistent state under transient DB errors, invisible due to broad exception swallowing.
- Priority: High

**`gateway/platforms/api_server.py` — Auth Edge Cases:**
- What's not tested: Timing attack resistance (no `compare_digest`), behavior with empty or malformed Authorization headers beyond the basic cases.
- Files: `gateway/platforms/api_server.py`
- Risk: Subtle auth bypass under non-standard header values.
- Priority: Medium

**`tools/code_execution_tool.py` — Tempdir Leak on Exception:**
- What's not tested: Cleanup behavior when an exception is raised between `mkdtemp` and the cleanup call.
- Files: `tools/code_execution_tool.py` lines 388, 645
- Risk: Disk space leak over many failed executions.
- Priority: Low

---

*Concerns audit: 2026-03-30*
