"""Tests for :mod:`agentops.utils.foundry_discovery`."""

from __future__ import annotations

from unittest import mock

import pytest


def test_returns_none_when_endpoint_empty():
    from agentops.utils.foundry_discovery import resolve_appinsights_connection

    assert resolve_appinsights_connection("") is None


def test_returns_none_when_sdk_missing(monkeypatch):
    """Simulate azure-ai-projects not being installed."""
    import sys

    monkeypatch.setitem(sys.modules, "azure.ai.projects", None)
    monkeypatch.setitem(sys.modules, "azure.identity", None)

    from agentops.utils import foundry_discovery

    # The import inside the function will raise ImportError because
    # ``None`` is registered in sys.modules.
    assert foundry_discovery.resolve_appinsights_connection(
        "https://x.services.ai.azure.com/api/projects/p"
    ) is None


def test_returns_connection_string_from_telemetry_get_connection_string():
    """Happy path: AIProjectClient.telemetry.get_connection_string() works."""
    fake_telemetry = mock.MagicMock()
    fake_telemetry.get_connection_string.return_value = (
        "InstrumentationKey=abc-123;IngestionEndpoint=https://example.in"
    )

    fake_client = mock.MagicMock()
    fake_client.telemetry = fake_telemetry

    fake_projects_mod = mock.MagicMock()
    fake_projects_mod.AIProjectClient.return_value = fake_client
    fake_identity_mod = mock.MagicMock()

    with mock.patch.dict(
        "sys.modules",
        {
            "azure.ai.projects": fake_projects_mod,
            "azure.identity": fake_identity_mod,
        },
    ):
        from agentops.utils.foundry_discovery import resolve_appinsights_connection

        result = resolve_appinsights_connection(
            "https://contoso.services.ai.azure.com/api/projects/p"
        )

    assert result == "InstrumentationKey=abc-123;IngestionEndpoint=https://example.in"
    fake_projects_mod.AIProjectClient.assert_called_once()
    _, kwargs = fake_projects_mod.AIProjectClient.call_args
    assert kwargs["endpoint"].endswith("/api/projects/p")


def test_falls_through_aliases_when_primary_method_missing():
    """Older SDKs use get_application_insights_connection_string."""
    fake_telemetry = mock.MagicMock(spec=["get_application_insights_connection_string"])
    fake_telemetry.get_application_insights_connection_string.return_value = (
        "InstrumentationKey=xyz"
    )

    fake_client = mock.MagicMock()
    fake_client.telemetry = fake_telemetry

    fake_projects_mod = mock.MagicMock()
    fake_projects_mod.AIProjectClient.return_value = fake_client
    fake_identity_mod = mock.MagicMock()

    with mock.patch.dict(
        "sys.modules",
        {
            "azure.ai.projects": fake_projects_mod,
            "azure.identity": fake_identity_mod,
        },
    ):
        from agentops.utils.foundry_discovery import resolve_appinsights_connection

        result = resolve_appinsights_connection(
            "https://x.services.ai.azure.com/api/projects/p"
        )

    assert result == "InstrumentationKey=xyz"


def test_returns_none_when_no_telemetry_attribute_on_client():
    """Very old SDK without a .telemetry helper at all."""
    fake_client = mock.MagicMock(spec=[])  # no telemetry attribute

    fake_projects_mod = mock.MagicMock()
    fake_projects_mod.AIProjectClient.return_value = fake_client
    fake_identity_mod = mock.MagicMock()

    with mock.patch.dict(
        "sys.modules",
        {
            "azure.ai.projects": fake_projects_mod,
            "azure.identity": fake_identity_mod,
        },
    ):
        from agentops.utils.foundry_discovery import resolve_appinsights_connection

        result = resolve_appinsights_connection(
            "https://x.services.ai.azure.com/api/projects/p"
        )

    assert result is None


def test_swallows_runtime_errors_from_telemetry_call():
    """A 4xx/5xx from get_connection_string must not propagate."""
    fake_telemetry = mock.MagicMock()
    fake_telemetry.get_connection_string.side_effect = RuntimeError("403")

    fake_client = mock.MagicMock()
    fake_client.telemetry = fake_telemetry

    fake_projects_mod = mock.MagicMock()
    fake_projects_mod.AIProjectClient.return_value = fake_client
    fake_identity_mod = mock.MagicMock()

    with mock.patch.dict(
        "sys.modules",
        {
            "azure.ai.projects": fake_projects_mod,
            "azure.identity": fake_identity_mod,
        },
    ):
        from agentops.utils.foundry_discovery import resolve_appinsights_connection

        result = resolve_appinsights_connection(
            "https://x.services.ai.azure.com/api/projects/p"
        )

    assert result is None


def test_from_env_uses_env_var(monkeypatch):
    """resolve_appinsights_connection_from_env reads the right env var."""
    monkeypatch.setenv(
        "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT",
        "https://x.services.ai.azure.com/api/projects/p",
    )

    fake_telemetry = mock.MagicMock()
    fake_telemetry.get_connection_string.return_value = "InstrumentationKey=via-env"

    fake_client = mock.MagicMock()
    fake_client.telemetry = fake_telemetry

    fake_projects_mod = mock.MagicMock()
    fake_projects_mod.AIProjectClient.return_value = fake_client
    fake_identity_mod = mock.MagicMock()

    with mock.patch.dict(
        "sys.modules",
        {
            "azure.ai.projects": fake_projects_mod,
            "azure.identity": fake_identity_mod,
        },
    ):
        from agentops.utils.foundry_discovery import (
            resolve_appinsights_connection_from_env,
        )

        assert resolve_appinsights_connection_from_env() == "InstrumentationKey=via-env"


def test_from_env_returns_none_when_env_unset(monkeypatch):
    monkeypatch.delenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", raising=False)

    from agentops.utils.foundry_discovery import resolve_appinsights_connection_from_env

    assert resolve_appinsights_connection_from_env() is None
