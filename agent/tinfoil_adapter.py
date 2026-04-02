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
        # TinfoilAI wraps an inner OpenAI client as self.client but does not
        # proxy the models resource onto itself — access it via client.client.
        models_page = client.client.models.list()
        return [m.id for m in models_page.data if getattr(m, "id", None)]
    except Exception as exc:
        logger.debug("Tinfoil model listing failed: %s", exc)
        return []
