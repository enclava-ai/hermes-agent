"""Tests for agent.tinfoil_adapter — specifically list_models() correctness.

Regression test for: "No models returned. Check your API key." when verifying
a Tinfoil API key from the dashboard.

Root cause: TinfoilAI SDK only proxies chat/embeddings/audio onto the wrapper
object; the models resource lives on the inner `.client` (OpenAI). Calling
`client.models.list()` raised AttributeError, caught silently, returning [].
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class TestListModels:
    def _make_fake_tinfoil_client(self, model_ids: list[str]) -> MagicMock:
        """Build a fake TinfoilAI instance that mirrors the SDK structure.

        The real TinfoilAI stores the OpenAI client as self.client and does NOT
        expose self.models directly — only self.client.models exists.
        """
        fake_model = lambda mid: SimpleNamespace(id=mid)
        fake_models_page = SimpleNamespace(data=[fake_model(m) for m in model_ids])

        inner_client = MagicMock()
        inner_client.models.list.return_value = fake_models_page

        outer_client = MagicMock(spec=[])  # no .models attribute on the outer object
        outer_client.client = inner_client
        return outer_client

    def test_list_models_returns_ids_from_inner_client(self):
        """list_models() must return model IDs via client.client.models.list()."""
        fake_client = self._make_fake_tinfoil_client(["llama3-3-70b", "whisper-large-v3-turbo"])

        with patch("agent.tinfoil_adapter.build_client", return_value=fake_client):
            from agent.tinfoil_adapter import list_models

            result = list_models("tf-test-key")

        assert result == ["llama3-3-70b", "whisper-large-v3-turbo"]

    def test_list_models_does_not_call_outer_models(self):
        """Calling client.models must not be attempted — it does not exist on TinfoilAI."""
        fake_client = self._make_fake_tinfoil_client(["llama3-3-70b"])

        # Verify the outer client has no .models attribute (mirrors real SDK)
        assert not hasattr(fake_client, "models") or isinstance(
            getattr(type(fake_client), "models", None), MagicMock
        )

        with patch("agent.tinfoil_adapter.build_client", return_value=fake_client):
            from agent.tinfoil_adapter import list_models

            result = list_models("tf-test-key")

        # Should succeed — not return [] due to AttributeError
        assert result

    def test_list_models_returns_empty_on_real_exception(self):
        """Genuine errors (network, auth) still return [] without crashing."""
        fake_client = MagicMock()
        fake_client.client.models.list.side_effect = RuntimeError("enclave unreachable")

        with patch("agent.tinfoil_adapter.build_client", return_value=fake_client):
            from agent.tinfoil_adapter import list_models

            result = list_models("tf-bad-key")

        assert result == []

    def test_list_models_filters_entries_without_id(self):
        """Models without an id field are excluded from results."""
        inner_client = MagicMock()
        inner_client.models.list.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(id="llama3-3-70b"),
                SimpleNamespace(),  # no .id attribute
                SimpleNamespace(id=None),
            ]
        )
        fake_client = MagicMock(spec=[])
        fake_client.client = inner_client

        with patch("agent.tinfoil_adapter.build_client", return_value=fake_client):
            from agent.tinfoil_adapter import list_models

            result = list_models("tf-test-key")

        assert result == ["llama3-3-70b"]
