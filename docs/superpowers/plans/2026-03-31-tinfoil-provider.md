# Tinfoil Provider Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Tinfoil as a first-class confidential-inference provider in hermes-agent using a dedicated `api_mode: "tinfoil"` that guarantees all inference requests stay on the `TinfoilAI` client and never silently fall back to OpenRouter or other providers.

**Architecture:** A new `api_mode: "tinfoil"` is registered alongside the existing `"anthropic_messages"` mode. The `TinfoilAI` client (from the `tinfoil` package) is instantiated in a thin adapter at `agent/tinfoil_adapter.py` and stored as `self._tinfoil_client` on `AIAgent`. All call-site branches in `run_agent.py`, `auxiliary_client.py`, and the setup wizard mirror the Anthropic-mode pattern: explicit client type, no silent fallback.

**Tech Stack:** Python 3.11+, `tinfoil>=0.11.0` (wraps `openai`), pytest, existing Hermes patterns (`ProviderConfig`, `resolve_runtime_provider`, `_interruptible_api_call`, `_interruptible_streaming_api_call`).

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `pyproject.toml` | Modify | Add `tinfoil` to core dependencies |
| `hermes_cli/auth.py` | Modify | Register `ProviderConfig(id="tinfoil", ...)` in `PROVIDER_REGISTRY` |
| `hermes_cli/runtime_provider.py` | Modify | Add `"tinfoil"` to `_VALID_API_MODES`; add resolution branch |
| `agent/tinfoil_adapter.py` | Create | `build_client`, `create_chat_completion`, `stream_chat_completion`, `list_models` |
| `run_agent.py` | Modify | Accept `"tinfoil"` api_mode; init `self._tinfoil_client`; dispatch in call/stream paths |
| `agent/auxiliary_client.py` | Modify | `_try_tinfoil()`; handle `"tinfoil"` and `"main"`-when-tinfoil in `_resolve_forced_provider` |
| `hermes_cli/models.py` | Modify | Add `"tinfoil"` key to `_PROVIDER_MODELS` (dynamic, fetched from adapter) |
| `hermes_cli/setup.py` | Modify | Add `_DEFAULT_PROVIDER_MODELS["tinfoil"]` fallback; add tinfoil branch in `_setup_provider_model_selection` |
| `cli-config.yaml.example` | Modify | Document `provider: "tinfoil"` |
| `tests/test_tinfoil_provider.py` | Create | Registry, resolution, missing-key error |
| `tests/test_tinfoil_adapter.py` | Create | `build_client`, non-streaming call, streaming chunks, `list_models` |
| `tests/test_run_agent_tinfoil.py` | Create | Init, non-streaming dispatch, streaming dispatch, fail-closed retry |
| `tests/agent/test_auxiliary_client_tinfoil.py` | Create | `_try_tinfoil`, forced-provider routing, vision failure path |

---

## Task 1: Add tinfoil dependency

**Files:**
- Modify: `pyproject.toml:13-37`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add `tinfoil>=0.11.0` to the `dependencies` list after the `anthropic` line:

```toml
  "anthropic>=0.39.0,<1",
  "tinfoil>=0.11.0",
```

- [ ] **Step 2: Verify the package installs**

```bash
cd /home/lio/s/p/flow/hermes-agent
pip install tinfoil>=0.11.0 --quiet && python -c "from tinfoil import TinfoilAI; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
cd /home/lio/s/p/flow/hermes-agent
git add pyproject.toml
git commit -m "deps: add tinfoil>=0.11.0 to core dependencies"
```

---

## Task 2: Register Tinfoil in PROVIDER_REGISTRY

**Files:**
- Modify: `hermes_cli/auth.py:215-223`
- Test: `tests/test_tinfoil_provider.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tinfoil_provider.py`:

```python
"""Tests for Tinfoil provider registration and runtime resolution."""
from __future__ import annotations

import pytest
from hermes_cli.auth import PROVIDER_REGISTRY, ProviderConfig


class TestTinfoilRegistry:
    def test_tinfoil_in_registry(self):
        assert "tinfoil" in PROVIDER_REGISTRY

    def test_tinfoil_is_api_key_provider(self):
        cfg = PROVIDER_REGISTRY["tinfoil"]
        assert cfg.auth_type == "api_key"

    def test_tinfoil_has_api_key_env_vars(self):
        cfg = PROVIDER_REGISTRY["tinfoil"]
        assert "TINFOIL_API_KEY" in cfg.api_key_env_vars
        assert "TINFOIL_TOKEN" in cfg.api_key_env_vars

    def test_tinfoil_has_inference_base_url(self):
        cfg = PROVIDER_REGISTRY["tinfoil"]
        assert cfg.inference_base_url == "https://inference.tinfoil.sh"

    def test_tinfoil_config_is_provider_config_instance(self):
        cfg = PROVIDER_REGISTRY["tinfoil"]
        assert isinstance(cfg, ProviderConfig)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/test_tinfoil_provider.py::TestTinfoilRegistry -v 2>&1 | head -30
```

Expected: FAILED with `KeyError: 'tinfoil'`

- [ ] **Step 3: Add ProviderConfig to PROVIDER_REGISTRY**

In `hermes_cli/auth.py`, add the following entry after the `"huggingface"` entry (after line 222), before the closing `}` of `PROVIDER_REGISTRY`:

```python
    "tinfoil": ProviderConfig(
        id="tinfoil",
        name="Tinfoil (Confidential AI)",
        auth_type="api_key",
        inference_base_url="https://inference.tinfoil.sh",
        api_key_env_vars=("TINFOIL_API_KEY", "TINFOIL_TOKEN"),
    ),
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/test_tinfoil_provider.py::TestTinfoilRegistry -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd /home/lio/s/p/flow/hermes-agent
git add hermes_cli/auth.py tests/test_tinfoil_provider.py
git commit -m "feat(tinfoil): register tinfoil in PROVIDER_REGISTRY"
```

---

## Task 3: Add runtime resolution branch

**Files:**
- Modify: `hermes_cli/runtime_provider.py:100`
- Test: `tests/test_tinfoil_provider.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_tinfoil_provider.py`:

```python
import os
from unittest.mock import patch


class TestTinfoilRuntimeResolution:
    def test_resolves_api_mode_tinfoil(self, monkeypatch):
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="tinfoil")
        assert result["api_mode"] == "tinfoil"

    def test_resolves_provider_name(self, monkeypatch):
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="tinfoil")
        assert result["provider"] == "tinfoil"

    def test_resolves_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="tinfoil")
        assert result["api_key"] == "tf-test-key"

    def test_resolves_api_key_from_fallback_env(self, monkeypatch):
        monkeypatch.delenv("TINFOIL_API_KEY", raising=False)
        monkeypatch.setenv("TINFOIL_TOKEN", "tf-token-fallback")
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="tinfoil")
        assert result["api_key"] == "tf-token-fallback"

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("TINFOIL_API_KEY", raising=False)
        monkeypatch.delenv("TINFOIL_TOKEN", raising=False)
        from hermes_cli.runtime_provider import resolve_runtime_provider
        from hermes_cli.auth import AuthError
        with pytest.raises(AuthError):
            resolve_runtime_provider(requested="tinfoil")

    def test_tinfoil_not_in_auto_fallback(self, monkeypatch):
        """Tinfoil should never be selected via 'auto' provider."""
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="auto")
        assert result.get("provider") != "tinfoil"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/test_tinfoil_provider.py::TestTinfoilRuntimeResolution -v 2>&1 | head -30
```

Expected: FAILs with `AssertionError` (api_mode is not "tinfoil") or `KeyError`

- [ ] **Step 3: Add "tinfoil" to _VALID_API_MODES**

In `hermes_cli/runtime_provider.py`, change line 100:

```python
_VALID_API_MODES = {"chat_completions", "codex_responses", "anthropic_messages", "tinfoil"}
```

- [ ] **Step 4: Add the tinfoil resolution branch**

In `hermes_cli/runtime_provider.py`, add the following block inside `resolve_runtime_provider()`, after the Anthropic branch (after line 387) and before the API-key providers catch-all:

```python
    # Tinfoil (Confidential AI — enclave-verified inference)
    if provider == "tinfoil":
        creds = resolve_api_key_provider_credentials("tinfoil")
        api_key = creds.get("api_key", "")
        if not api_key:
            raise AuthError(
                "No Tinfoil credentials found. Set TINFOIL_API_KEY in your environment. "
                "Get an API key at https://tinfoil.sh"
            )
        return {
            "provider": "tinfoil",
            "api_mode": "tinfoil",
            "api_key": api_key,
            "base_url": "https://inference.tinfoil.sh",
            "source": creds.get("source", "env"),
            "requested_provider": requested_provider,
        }
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/test_tinfoil_provider.py -v
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
cd /home/lio/s/p/flow/hermes-agent
git add hermes_cli/runtime_provider.py tests/test_tinfoil_provider.py
git commit -m "feat(tinfoil): add runtime resolution branch, api_mode tinfoil"
```

---

## Task 4: Create the tinfoil adapter

**Files:**
- Create: `agent/tinfoil_adapter.py`
- Test: `tests/test_tinfoil_adapter.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tinfoil_adapter.py`:

```python
"""Tests for agent/tinfoil_adapter.py — all tests mock TinfoilAI."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call
import pytest


def _make_mock_tinfoil_client(models=None, completion_text="hello"):
    """Build a mock TinfoilAI client that returns plausible responses."""
    client = MagicMock()

    # models.list()
    model_objs = [SimpleNamespace(id=m) for m in (models or ["llama3-3-70b"])]
    client.models.list.return_value = SimpleNamespace(data=model_objs)

    # chat.completions.create() non-streaming
    choice = SimpleNamespace(
        index=0,
        message=SimpleNamespace(content=completion_text, role="assistant", tool_calls=None),
        finish_reason="stop",
    )
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[choice],
        model="llama3-3-70b",
        usage=usage,
    )
    return client


class TestBuildClient:
    def test_returns_tinfoil_ai_instance(self):
        mock_cls = MagicMock()
        with patch("agent.tinfoil_adapter._TinfoilAI", mock_cls):
            from agent.tinfoil_adapter import build_client
            build_client("tf-key-123")
        mock_cls.assert_called_once_with(api_key="tf-key-123")

    def test_raises_import_error_when_sdk_missing(self):
        with patch("agent.tinfoil_adapter._TinfoilAI", None):
            from agent.tinfoil_adapter import build_client
            with pytest.raises(ImportError, match="tinfoil"):
                build_client("tf-key-123")


class TestCreateChatCompletion:
    def test_delegates_to_client(self):
        from agent.tinfoil_adapter import create_chat_completion
        mock_client = _make_mock_tinfoil_client()
        result = create_chat_completion(
            mock_client,
            model="llama3-3-70b",
            messages=[{"role": "user", "content": "hi"}],
        )
        mock_client.chat.completions.create.assert_called_once_with(
            model="llama3-3-70b",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert result.choices[0].message.content == "hello"

    def test_passes_through_kwargs(self):
        from agent.tinfoil_adapter import create_chat_completion
        mock_client = _make_mock_tinfoil_client()
        create_chat_completion(
            mock_client,
            model="llama3-3-70b",
            messages=[],
            temperature=0.7,
            max_tokens=512,
        )
        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 512


class TestStreamChatCompletion:
    def test_yields_chunks_from_stream(self):
        from agent.tinfoil_adapter import stream_chat_completion
        mock_client = MagicMock()

        chunk1 = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="hel"), finish_reason=None)])
        chunk2 = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="lo"), finish_reason="stop")])
        mock_client.chat.completions.create.return_value = iter([chunk1, chunk2])

        chunks = list(stream_chat_completion(
            mock_client,
            model="llama3-3-70b",
            messages=[{"role": "user", "content": "hi"}],
        ))
        assert len(chunks) == 2
        assert chunks[0].choices[0].delta.content == "hel"
        assert chunks[1].choices[0].delta.content == "lo"

    def test_sets_stream_true(self):
        from agent.tinfoil_adapter import stream_chat_completion
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter([])
        list(stream_chat_completion(mock_client, model="m", messages=[]))
        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs.get("stream") is True


class TestListModels:
    def test_returns_model_ids(self):
        from agent.tinfoil_adapter import list_models
        mock_cls = MagicMock(return_value=_make_mock_tinfoil_client(models=["llama3-3-70b", "mistral-7b"]))
        with patch("agent.tinfoil_adapter._TinfoilAI", mock_cls):
            result = list_models("tf-key-123")
        assert result == ["llama3-3-70b", "mistral-7b"]

    def test_returns_empty_list_on_error(self):
        from agent.tinfoil_adapter import list_models
        mock_cls = MagicMock(side_effect=Exception("network error"))
        with patch("agent.tinfoil_adapter._TinfoilAI", mock_cls):
            result = list_models("tf-key-123")
        assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/test_tinfoil_adapter.py -v 2>&1 | head -20
```

Expected: FAILED with `ModuleNotFoundError: No module named 'agent.tinfoil_adapter'`

- [ ] **Step 3: Create agent/tinfoil_adapter.py**

```python
"""Tinfoil confidential inference adapter for Hermes Agent.

Wraps TinfoilAI (the tinfoil-python SDK) for use as a first-class api_mode
in hermes-agent.  All inference calls in this mode stay on the TinfoilAI
client, which handles enclave router selection, attestation via GitHub +
Sigstore, and TLS certificate pinning.  No fallback to generic OpenAI clients.

Public API:
  build_client(api_key)                          -> TinfoilAI
  create_chat_completion(client, **kwargs)        -> response
  stream_chat_completion(client, **kwargs)        -> Iterator[chunk]
  list_models(api_key)                           -> list[str]
"""

from __future__ import annotations

import logging
from typing import Any, Iterator, List

logger = logging.getLogger(__name__)

try:
    from tinfoil import TinfoilAI as _TinfoilAI
except ImportError:
    _TinfoilAI = None  # type: ignore[assignment]


def build_client(api_key: str) -> Any:
    """Instantiate a TinfoilAI client with repo-based enclave attestation.

    The SDK auto-selects a verified router via https://atc.tinfoil.sh/routers,
    fetches a Sigstore-attested digest from GitHub, and pins the TLS certificate
    to the enclave's public key.  No enclave address needed from the caller.

    Args:
        api_key: Tinfoil API key (TINFOIL_API_KEY or TINFOIL_TOKEN).

    Returns:
        A TinfoilAI client instance (OpenAI-compatible interface).

    Raises:
        ImportError: If the tinfoil package is not installed.
    """
    if _TinfoilAI is None:
        raise ImportError(
            "The 'tinfoil' package is required for the Tinfoil provider. "
            "Install it with: pip install 'tinfoil>=0.11.0'"
        )
    return _TinfoilAI(api_key=api_key)


def create_chat_completion(client: Any, **kwargs: Any) -> Any:
    """Execute a non-streaming chat completion through the Tinfoil client.

    Accepts the same kwargs as openai.chat.completions.create().
    The payload is standard OpenAI chat-completions format — no translation needed.

    Args:
        client: A TinfoilAI client returned by build_client().
        **kwargs: Standard chat completions parameters (model, messages, tools, etc.).

    Returns:
        OpenAI-compatible response object with .choices[0].message.content.
    """
    return client.chat.completions.create(**kwargs)


def stream_chat_completion(client: Any, **kwargs: Any) -> Iterator[Any]:
    """Execute a streaming chat completion through the Tinfoil client.

    Yields OpenAI-compatible chunks with .choices[0].delta.content.

    Args:
        client: A TinfoilAI client returned by build_client().
        **kwargs: Standard chat completions parameters. `stream` is forced True.

    Yields:
        OpenAI-compatible stream chunks.
    """
    kwargs["stream"] = True
    stream = client.chat.completions.create(**kwargs)
    yield from stream


def list_models(api_key: str) -> List[str]:
    """Fetch available Tinfoil model IDs through the Tinfoil client.

    Used by setup and model-selection flows.  Returns an empty list on any
    error so callers can fall back to a default list without crashing.

    Args:
        api_key: Tinfoil API key.

    Returns:
        List of model ID strings (e.g. ["llama3-3-70b", "whisper-large-v3-turbo"]).
    """
    try:
        client = build_client(api_key)
        models_page = client.models.list()
        return [m.id for m in models_page.data if getattr(m, "id", None)]
    except Exception as exc:
        logger.debug("Tinfoil model listing failed: %s", exc)
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/test_tinfoil_adapter.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
cd /home/lio/s/p/flow/hermes-agent
git add agent/tinfoil_adapter.py tests/test_tinfoil_adapter.py
git commit -m "feat(tinfoil): add tinfoil_adapter with build_client, completion helpers, list_models"
```

---

## Task 5: Wire tinfoil mode into AIAgent (run_agent.py)

**Files:**
- Modify: `run_agent.py:587-603` (api_mode validation), `run_agent.py:784-807` (client init), `run_agent.py:3797-3839` (`_interruptible_api_call`), `run_agent.py:3894-3925` (`_interruptible_streaming_api_call`)
- Test: `tests/test_run_agent_tinfoil.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_run_agent_tinfoil.py`:

```python
"""Tests for Tinfoil mode wiring in AIAgent — fail-closed behavior."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest


def _make_tinfoil_agent():
    """Build an AIAgent configured for tinfoil mode, with mocked adapter."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content="ok", role="assistant", tool_calls=None),
            finish_reason="stop",
            index=0,
        )],
        model="llama3-3-70b",
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3, total_tokens=8),
    )
    with patch("agent.tinfoil_adapter.build_client", return_value=mock_client):
        from run_agent import AIAgent
        agent = AIAgent(
            model="llama3-3-70b",
            api_key="tf-key-123",
            base_url="https://inference.tinfoil.sh",
            provider="tinfoil",
            api_mode="tinfoil",
            quiet_mode=True,
        )
    agent._tinfoil_client = mock_client
    return agent, mock_client


class TestTinfoilAgentInit:
    def test_api_mode_is_tinfoil(self):
        agent, _ = _make_tinfoil_agent()
        assert agent.api_mode == "tinfoil"

    def test_openai_client_is_none(self):
        agent, _ = _make_tinfoil_agent()
        # For tinfoil mode, the generic OpenAI client must not be initialized
        assert agent.client is None

    def test_tinfoil_client_is_set(self):
        agent, mock_client = _make_tinfoil_agent()
        assert agent._tinfoil_client is mock_client


class TestTinfoilNonStreamingCall:
    def test_dispatches_to_tinfoil_adapter(self):
        agent, mock_client = _make_tinfoil_agent()
        api_kwargs = {
            "model": "llama3-3-70b",
            "messages": [{"role": "user", "content": "hi"}],
        }
        with patch("agent.tinfoil_adapter.create_chat_completion",
                   return_value=mock_client.chat.completions.create.return_value) as mock_call:
            response = agent._interruptible_api_call(api_kwargs)
        mock_call.assert_called_once_with(mock_client, **api_kwargs)
        assert response.choices[0].message.content == "ok"

    def test_does_not_use_openai_client(self):
        agent, mock_client = _make_tinfoil_agent()
        with patch("agent.tinfoil_adapter.create_chat_completion",
                   return_value=mock_client.chat.completions.create.return_value):
            agent._interruptible_api_call({
                "model": "llama3-3-70b",
                "messages": [],
            })
        # The generic OpenAI client must never be called
        assert agent.client is None


class TestTinfoilFailClosed:
    def test_tinfoil_error_does_not_fall_back_to_openrouter(self):
        """An error in tinfoil mode must not silently route to OpenRouter."""
        agent, mock_client = _make_tinfoil_agent()
        with patch("agent.tinfoil_adapter.create_chat_completion",
                   side_effect=Exception("attestation failed")):
            with pytest.raises(Exception, match="attestation failed"):
                agent._interruptible_api_call({
                    "model": "llama3-3-70b",
                    "messages": [],
                })
        # Verify no OpenAI client was created as a fallback
        assert agent.client is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/test_run_agent_tinfoil.py -v 2>&1 | head -30
```

Expected: FAILED — `api_mode` gets overwritten or `_tinfoil_client` doesn't exist.

- [ ] **Step 3: Accept "tinfoil" as valid api_mode in AIAgent.__init__**

In `run_agent.py`, change line 587 from:

```python
        if api_mode in {"chat_completions", "codex_responses", "anthropic_messages"}:
```

to:

```python
        if api_mode in {"chat_completions", "codex_responses", "anthropic_messages", "tinfoil"}:
```

- [ ] **Step 4: Add tinfoil client init branch**

In `run_agent.py`, change the existing block at line 784:

```python
        self._anthropic_client = None
        self._is_anthropic_oauth = False

        if self.api_mode == "anthropic_messages":
```

to:

```python
        self._anthropic_client = None
        self._is_anthropic_oauth = False
        self._tinfoil_client = None

        if self.api_mode == "tinfoil":
            from agent.tinfoil_adapter import build_client as _tinfoil_build
            if not api_key:
                raise RuntimeError(
                    "Tinfoil mode requires TINFOIL_API_KEY. "
                    "Set it in your environment or run 'hermes model' to reconfigure."
                )
            self.api_key = api_key
            self._tinfoil_client = _tinfoil_build(api_key)
            self.client = None
            self._client_kwargs = {}
            if not self.quiet_mode:
                print(f"🤖 AI Agent initialized with model: {self.model} (Tinfoil confidential)")
        elif self.api_mode == "anthropic_messages":
```

- [ ] **Step 5: Add tinfoil branch to _interruptible_api_call**

In `run_agent.py`, change the `_call()` inner function at lines 3795-3808 (inside `_interruptible_api_call`):

```python
        def _call():
            try:
                if self.api_mode == "codex_responses":
                    request_client_holder["client"] = self._create_request_openai_client(reason="codex_stream_request")
                    result["response"] = self._run_codex_stream(
                        api_kwargs,
                        client=request_client_holder["client"],
                        on_first_delta=getattr(self, "_codex_on_first_delta", None),
                    )
                elif self.api_mode == "anthropic_messages":
                    result["response"] = self._anthropic_messages_create(api_kwargs)
                elif self.api_mode == "tinfoil":
                    from agent.tinfoil_adapter import create_chat_completion
                    result["response"] = create_chat_completion(self._tinfoil_client, **api_kwargs)
                else:
                    request_client_holder["client"] = self._create_request_openai_client(reason="chat_completion_request")
                    result["response"] = request_client_holder["client"].chat.completions.create(**api_kwargs)
```

- [ ] **Step 6: Add tinfoil streaming support in _interruptible_streaming_api_call**

`TinfoilAI` is an `OpenAI` subclass — its streaming chunks have the same shape as regular `chat_completions` chunks. The cleanest approach is to reuse the existing `_call_chat_completions()` inner function but inject `self._tinfoil_client` instead of creating a new OpenAI client.

**6a.** In `run_agent.py`, inside `_call_chat_completions()` (the inner function inside `_interruptible_streaming_api_call`, around line 3956), change:

```python
            request_client_holder["client"] = self._create_request_openai_client(
                reason="chat_completion_stream_request"
            )
```

to:

```python
            if self.api_mode == "tinfoil":
                request_client_holder["client"] = self._tinfoil_client
            else:
                request_client_holder["client"] = self._create_request_openai_client(
                    reason="chat_completion_stream_request"
                )
```

**6b.** No other change needed in `_interruptible_streaming_api_call` — tinfoil naturally falls through to `_call_chat_completions()` since it has no early-return branch at the top of the function (unlike `codex_responses` and `anthropic_messages`).

**6c.** Also update the interrupt-handling block inside `_interruptible_streaming_api_call`. Find the interrupt section that closes and rebuilds the anthropic client on interrupt (around line 3825 in `_interruptible_api_call`). It currently reads:

```python
                    if self.api_mode == "anthropic_messages":
                        from agent.anthropic_adapter import build_anthropic_client

                        self._anthropic_client.close()
                        self._anthropic_client = build_anthropic_client(
                            self._anthropic_api_key,
                            getattr(self, "_anthropic_base_url", None),
                        )
                    else:
                        request_client = request_client_holder.get("client")
```

Change to:

```python
                    if self.api_mode == "anthropic_messages":
                        from agent.anthropic_adapter import build_anthropic_client

                        self._anthropic_client.close()
                        self._anthropic_client = build_anthropic_client(
                            self._anthropic_api_key,
                            getattr(self, "_anthropic_base_url", None),
                        )
                    elif self.api_mode == "tinfoil":
                        # Rebuild the Tinfoil client to get a fresh connection
                        # after an interrupt — do not fall back to any other provider.
                        from agent.tinfoil_adapter import build_client as _tinfoil_rebuild
                        self._tinfoil_client = _tinfoil_rebuild(self.api_key)
                    else:
                        request_client = request_client_holder.get("client")
```

In `run_agent.py` at line 3912, change:

```python
        if self.api_mode == "tinfoil":
            # TinfoilAI is OpenAI-compatible; delegate to _interruptible_api_call
            # which already has the tinfoil dispatch branch.  Streaming for
            # tinfoil uses TinfoilAI's native stream support via the same
            # _call_chat_completions path but with self._tinfoil_client.
            # TODO: wire streaming chunks through _call_chat_completions shim
            # For now, delegate non-streaming path while streaming shim is set up.
            return self._interruptible_api_call(api_kwargs)

        if self.api_mode == "codex_responses":
```

Actually let me look at `_call_chat_completions` more carefully to understand how to inject the tinfoil client. The function at line 3940 creates a new openai client via `self._create_request_openai_client`. We need a way to use `self._tinfoil_client` in the streaming path.

The cleanest way: add a check inside `_call_chat_completions` inner function: if `self.api_mode == "tinfoil"`, use `self._tinfoil_client` directly instead of creating a new openai client. Since `TinfoilAI` inherits from `OpenAI`, it has the exact same streaming interface.

Let me write the actual step 6 properly.

- [ ] **Step 6: Add tinfoil streaming support in _interruptible_streaming_api_call**

In `run_agent.py`, in the `_call_chat_completions()` inner function (around line 3940), change the line:

```python
            request_client_holder["client"] = self._create_request_openai_client(
                reason="chat_completion_stream_request"
            )
```

to:

```python
            if self.api_mode == "tinfoil":
                request_client_holder["client"] = self._tinfoil_client
            else:
                request_client_holder["client"] = self._create_request_openai_client(
                    reason="chat_completion_stream_request"
                )
```

And at line 3912, add a tinfoil early return that delegates to `_call_chat_completions`:

```python
        if self.api_mode == "tinfoil":
            # TinfoilAI is OpenAI-compatible. Fall through to _call_chat_completions()
            # below, which will use self._tinfoil_client for the stream.
            pass

        if self.api_mode == "codex_responses":
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/test_run_agent_tinfoil.py -v
```

Expected: all pass

- [ ] **Step 8: Commit**

```bash
cd /home/lio/s/p/flow/hermes-agent
git add run_agent.py tests/test_run_agent_tinfoil.py
git commit -m "feat(tinfoil): wire tinfoil api_mode into AIAgent init and call paths"
```

---

## Task 6: Auxiliary client fail-closed wiring

**Files:**
- Modify: `agent/auxiliary_client.py`
- Test: `tests/agent/test_auxiliary_client_tinfoil.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agent/test_auxiliary_client_tinfoil.py`:

```python
"""Tests for Tinfoil routing in auxiliary_client — fail-closed on vision fallback."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest


class TestTryTinfoil:
    def test_returns_client_and_model_when_key_set(self, monkeypatch):
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        mock_client = MagicMock()
        with patch("agent.tinfoil_adapter.build_client", return_value=mock_client):
            from agent.auxiliary_client import _try_tinfoil
            client, model = _try_tinfoil()
        assert client is not None
        assert isinstance(model, str) and model

    def test_returns_none_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("TINFOIL_API_KEY", raising=False)
        monkeypatch.delenv("TINFOIL_TOKEN", raising=False)
        from agent.auxiliary_client import _try_tinfoil
        client, model = _try_tinfoil()
        assert client is None
        assert model is None


class TestResolveForcedProviderTinfoil:
    def test_forced_tinfoil_resolves(self, monkeypatch):
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        mock_client = MagicMock()
        with patch("agent.tinfoil_adapter.build_client", return_value=mock_client):
            from agent.auxiliary_client import _resolve_forced_provider
            client, model = _resolve_forced_provider("tinfoil")
        assert client is not None

    def test_forced_main_uses_tinfoil_when_configured(self, monkeypatch):
        """When the main provider is Tinfoil, 'main' auxiliary must use Tinfoil too."""
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        mock_client = MagicMock()
        # Patch load_config at the source so all imports see the patched version
        mock_cfg = {"model": {"provider": "tinfoil", "default": "llama3-3-70b"}}
        with patch("hermes_cli.config.load_config", return_value=mock_cfg), \
             patch("agent.tinfoil_adapter.build_client", return_value=mock_client):
            from agent.auxiliary_client import _resolve_forced_provider
            client, model = _resolve_forced_provider("main")
        assert client is not None

    def test_vision_fails_when_tinfoil_active(self, monkeypatch):
        """Vision auxiliary must not fall back to OpenRouter when Tinfoil is the main provider."""
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        mock_cfg = {"model": {"provider": "tinfoil", "default": "llama3-3-70b"}}
        with patch("hermes_cli.config.load_config", return_value=mock_cfg):
            from agent.auxiliary_client import resolve_provider_client
            # Vision task for tinfoil should return None (unsupported), not fall to OpenRouter
            client, model = resolve_provider_client("tinfoil", task="vision")
        assert client is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/agent/test_auxiliary_client_tinfoil.py -v 2>&1 | head -20
```

Expected: FAILED — `_try_tinfoil` does not exist yet.

- [ ] **Step 3: Add _try_tinfoil() to auxiliary_client.py**

In `agent/auxiliary_client.py`, add the following after the `_try_anthropic` function (around line 704), and add `"tinfoil"` to `_API_KEY_PROVIDER_AUX_MODELS`:

First, add to the `_API_KEY_PROVIDER_AUX_MODELS` dict (around line 56):

```python
    "tinfoil": "llama3-3-70b",
```

Then add the helper function after `_try_anthropic`:

```python
def _try_tinfoil() -> Tuple[Optional[Any], Optional[str]]:
    """Try to build a Tinfoil auxiliary client from env credentials."""
    api_key = os.getenv("TINFOIL_API_KEY") or os.getenv("TINFOIL_TOKEN")
    if not api_key:
        return None, None
    try:
        from agent.tinfoil_adapter import build_client as _tinfoil_build
        client = _tinfoil_build(api_key.strip())
        model = _API_KEY_PROVIDER_AUX_MODELS.get("tinfoil", "llama3-3-70b")
        logger.debug("Auxiliary client: Tinfoil confidential (%s)", model)
        return client, model
    except Exception as exc:
        logger.debug("Tinfoil auxiliary client build failed: %s", exc)
        return None, None
```

- [ ] **Step 4: Add "tinfoil" to _resolve_forced_provider and update "main" branch**

In `agent/auxiliary_client.py`, in `_resolve_forced_provider()`, add a tinfoil branch after the `"nous"` branch (around line 715):

```python
    if forced == "tinfoil":
        client, model = _try_tinfoil()
        if client is None:
            logger.warning("auxiliary.provider=tinfoil but no Tinfoil credentials found (set TINFOIL_API_KEY)")
        return client, model
```

Also update the `"main"` branch to check if the configured provider is Tinfoil:

```python
    if forced == "main":
        # When the main provider is Tinfoil, auxiliary tasks must also use Tinfoil.
        # Do not silently route to OpenRouter — that would violate confidentiality.
        try:
            from hermes_cli.config import load_config as _load_config
            _cfg = _load_config()
            _model_cfg = _cfg.get("model", {})
            _main_provider = str(_model_cfg.get("provider") or "").strip().lower()
        except Exception:
            _main_provider = ""

        if _main_provider == "tinfoil":
            client, model = _try_tinfoil()
            if client is None:
                logger.warning("auxiliary.provider=main with tinfoil main provider but TINFOIL_API_KEY not set")
            return client, model

        # Original "main" fallback chain for non-Tinfoil providers
        for try_fn in (_try_custom_endpoint, _try_codex, _resolve_api_key_provider):
            client, model = try_fn()
            if client is not None:
                return client, model
        logger.warning("auxiliary.provider=main but no main endpoint credentials found")
        return None, None
```

- [ ] **Step 5: Add vision fail-closed guard in resolve_provider_client**

In `agent/auxiliary_client.py`, in `resolve_provider_client()`, add a guard that returns `(None, None)` for vision tasks when the active provider is Tinfoil:

```python
    # Tinfoil confidentiality guard: if the main provider is Tinfoil, vision
    # auxiliary must not fall back to OpenRouter or other non-confidential providers.
    # Return None rather than silently leaking data.
    if task == "vision":
        try:
            from hermes_cli.config import load_config as _load_cfg_vision
            _vcfg = _load_cfg_vision()
            _vprovider = str((_vcfg.get("model") or {}).get("provider") or "").strip().lower()
        except Exception:
            _vprovider = ""
        if _vprovider == "tinfoil" and provider not in ("tinfoil", "main"):
            logger.warning(
                "Vision auxiliary disabled: Tinfoil is active and vision is not yet "
                "supported through Tinfoil. Configure a non-Tinfoil main provider to enable vision."
            )
            return None, None
```

This block should be added near the top of `resolve_provider_client()`, after the forced-provider early return.

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/agent/test_auxiliary_client_tinfoil.py -v
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
cd /home/lio/s/p/flow/hermes-agent
git add agent/auxiliary_client.py tests/agent/test_auxiliary_client_tinfoil.py
git commit -m "feat(tinfoil): add fail-closed tinfoil routing in auxiliary_client"
```

---

## Task 7: Model catalog in models.py and setup.py

**Files:**
- Modify: `hermes_cli/models.py:57`
- Modify: `hermes_cli/setup.py:57-90`
- Test: `tests/test_tinfoil_provider.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_tinfoil_provider.py`:

```python
class TestTinfoilModelCatalog:
    def test_provider_models_has_tinfoil_key(self):
        from hermes_cli.models import _PROVIDER_MODELS
        assert "tinfoil" in _PROVIDER_MODELS

    def test_setup_default_models_has_tinfoil_fallback(self):
        from hermes_cli.setup import _DEFAULT_PROVIDER_MODELS
        assert "tinfoil" in _DEFAULT_PROVIDER_MODELS
        assert len(_DEFAULT_PROVIDER_MODELS["tinfoil"]) > 0

    def test_tinfoil_model_selection_uses_list_models(self, monkeypatch):
        """Setup must call list_models (not fetch_api_models) for tinfoil."""
        monkeypatch.setenv("TINFOIL_API_KEY", "tf-test-key")
        called_with = {}

        def _fake_list_models(api_key):
            called_with["api_key"] = api_key
            return ["llama3-3-70b", "mistral-7b-instruct"]

        import hermes_cli.setup as setup_mod
        monkeypatch.setattr(
            "hermes_cli.setup._tinfoil_list_models",
            _fake_list_models,
            raising=False,
        )

        choices = []
        def _fake_prompt_choice(question, options, default=0):
            choices.extend(options)
            return len(options) - 1  # "Keep current"

        def _fake_prompt_fn(q):
            return ""

        from hermes_cli.config import load_config, save_config
        cfg = load_config()
        setup_mod._setup_provider_model_selection(
            cfg, "tinfoil", "llama3-3-70b",
            _fake_prompt_choice, _fake_prompt_fn,
        )
        # list_models should have been called, not fetch_api_models
        assert called_with.get("api_key") == "tf-test-key"
        # The model list from list_models should appear in choices
        assert "llama3-3-70b" in choices
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/test_tinfoil_provider.py::TestTinfoilModelCatalog -v 2>&1 | head -20
```

Expected: FAILED — `_PROVIDER_MODELS` has no `"tinfoil"` key.

- [ ] **Step 3: Add tinfoil to _PROVIDER_MODELS in models.py**

In `hermes_cli/models.py`, add to the `_PROVIDER_MODELS` dict after the last entry:

```python
    "tinfoil": [],  # Populated dynamically via agent.tinfoil_adapter.list_models()
```

- [ ] **Step 4: Add tinfoil fallback in setup.py and tinfoil branch in _setup_provider_model_selection**

In `hermes_cli/setup.py`, add to `_DEFAULT_PROVIDER_MODELS`:

```python
    "tinfoil": [
        "llama3-3-70b",
        "llama3-1-405b",
        "mistral-7b-instruct",
    ],
```

Then add a tinfoil-specific model fetching path in `_setup_provider_model_selection`. After the existing `is_copilot_catalog_provider` block (around line 193), add:

```python
    # Tinfoil: fetch models through the Tinfoil client (not generic /models probe)
    is_tinfoil = provider_id == "tinfoil"
    if is_tinfoil:
        from hermes_cli.config import get_env_value
        api_key = get_env_value("TINFOIL_API_KEY") or os.getenv("TINFOIL_API_KEY", "")
        if not api_key:
            api_key = get_env_value("TINFOIL_TOKEN") or os.getenv("TINFOIL_TOKEN", "")
        try:
            from agent.tinfoil_adapter import list_models as _tinfoil_list_models
            live_models = _tinfoil_list_models(api_key) if api_key else []
        except Exception:
            live_models = []
```

And in the existing conditional that calls `fetch_api_models`, wrap it to skip for tinfoil:

```python
    if is_copilot_catalog_provider and catalog:
        live_models = [item.get("id", "") for item in catalog if item.get("id")]
    elif not is_tinfoil:
        live_models = fetch_api_models(api_key, base_url)
```

Also add a module-level shim for testability (at the top of `setup.py`, after the imports):

```python
# Shim for testing: tests can monkeypatch hermes_cli.setup._tinfoil_list_models
def _tinfoil_list_models(api_key: str):
    from agent.tinfoil_adapter import list_models
    return list_models(api_key)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/test_tinfoil_provider.py -v
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
cd /home/lio/s/p/flow/hermes-agent
git add hermes_cli/models.py hermes_cli/setup.py tests/test_tinfoil_provider.py
git commit -m "feat(tinfoil): add tinfoil model catalog and setup wizard integration"
```

---

## Task 8: Document in cli-config.yaml.example

**Files:**
- Modify: `cli-config.yaml.example:14-38`

- [ ] **Step 1: Add tinfoil to the provider comment block**

In `cli-config.yaml.example`, add `"tinfoil"` to the provider list comment (around line 25):

```yaml
  #   "tinfoil"      - Tinfoil confidential AI (requires: TINFOIL_API_KEY)
```

Place it after `"kilocode"` and before `#`.

- [ ] **Step 2: Add a tinfoil example section**

Near the end of the model configuration comment block, add:

```yaml
  #
  # Confidential inference (Tinfoil):
  #   provider: "tinfoil"
  #   default: "llama3-3-70b"
  #   # Set TINFOIL_API_KEY in ~/.hermes/.env
  #   # All requests are routed through a verified secure enclave.
```

- [ ] **Step 3: Commit**

```bash
cd /home/lio/s/p/flow/hermes-agent
git add cli-config.yaml.example
git commit -m "docs(tinfoil): document tinfoil provider in cli-config.yaml.example"
```

---

## Task 9: Full test run and smoke check

- [ ] **Step 1: Run all tinfoil tests together**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/test_tinfoil_provider.py tests/test_tinfoil_adapter.py tests/test_run_agent_tinfoil.py tests/agent/test_auxiliary_client_tinfoil.py -v
```

Expected: all pass, no errors

- [ ] **Step 2: Run full test suite to check for regressions**

```bash
cd /home/lio/s/p/flow/hermes-agent
python -m pytest tests/ -x -q 2>&1 | tail -20
```

Expected: no new failures compared to baseline (only tinfoil-specific tests should be new)

- [ ] **Step 3: Verify resolution smoke check**

```bash
cd /home/lio/s/p/flow/hermes-agent
TINFOIL_API_KEY=test-smoke python -c "
from hermes_cli.runtime_provider import resolve_runtime_provider
r = resolve_runtime_provider(requested='tinfoil')
assert r['api_mode'] == 'tinfoil', r
assert r['provider'] == 'tinfoil', r
assert r['api_key'] == 'test-smoke', r
print('resolution OK:', r)
"
```

Expected: `resolution OK: {'provider': 'tinfoil', 'api_mode': 'tinfoil', 'api_key': 'test-smoke', ...}`

- [ ] **Step 4: Commit**

```bash
cd /home/lio/s/p/flow/hermes-agent
git add .
git commit -m "feat(tinfoil): complete tinfoil provider integration"
```
