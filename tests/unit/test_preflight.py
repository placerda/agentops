"""Tests for :mod:`agentops.services.preflight`."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from agentops.services.preflight import (
    PreflightCheck,
    PreflightReport,
    _check_application_insights_env,
    _check_azure_cli,
    _check_foundry_project,
    _check_workspace,
    format_report,
    run_preflight,
)


def test_workspace_check_passes_for_init_workspace(tmp_path: Path) -> None:
    (tmp_path / ".agentops").mkdir()
    c = _check_workspace(tmp_path)
    assert c.status == "ok"


def test_workspace_check_warns_when_not_initialized(tmp_path: Path) -> None:
    c = _check_workspace(tmp_path)
    assert c.status == "warn"
    assert "agentops init" in c.message


def test_workspace_check_fails_for_missing_dir(tmp_path: Path) -> None:
    c = _check_workspace(tmp_path / "does-not-exist")
    assert c.status == "fail"


def test_azure_cli_check_humanizes_az_login_failure() -> None:
    """When DefaultAzureCredential reports `AzureCliCredential: Failed
    to invoke the Azure CLI`, the pre-flight tile must offer the
    `az login` remediation, not the wall of text."""

    class _FakeCred:
        def __init__(self, **_kw):
            pass
        def get_token(self, _scope):
            raise RuntimeError(
                "DefaultAzureCredential failed to retrieve a token "
                "from the included credentials. AzureCliCredential: "
                "Failed to invoke the Azure CLI. ...lots of text..."
            )

    with mock.patch("azure.identity.DefaultAzureCredential", _FakeCred):
        c = _check_azure_cli()
    assert c.status == "fail"
    assert "az login" in c.message
    assert "DefaultAzureCredential" not in c.message


def test_foundry_project_skip_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", raising=False)
    c = _check_foundry_project()
    assert c.status == "skip"


def test_application_insights_ok_when_env_var_set(monkeypatch) -> None:
    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=11111111-2222-3333-4444-555555555555",
    )
    c = _check_application_insights_env()
    assert c.status == "ok"


def test_application_insights_warns_when_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", raising=False)
    c = _check_application_insights_env()
    assert c.status == "warn"
    assert "App Insights" in c.message


def test_run_preflight_collects_all_checks(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".agentops").mkdir()
    # Force every Azure-dependent check into a deterministic state.
    monkeypatch.delenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

    class _FakeCred:
        def __init__(self, **_kw):
            pass
        def get_token(self, _scope):
            class _T:
                token = "fake"
                expires_on = 9999999999
            return _T()

    with mock.patch("azure.identity.DefaultAzureCredential", _FakeCred):
        report = run_preflight(tmp_path, scope="doctor")
    names = [c.name for c in report.checks]
    assert names == ["workspace", "azure_auth", "foundry_project", "app_insights"]
    assert not report.has_failures
    assert report.has_warnings  # app_insights and foundry_project are skip/warn


def test_format_report_renders_status_glyphs() -> None:
    report = PreflightReport(checks=[
        PreflightCheck(name="workspace", status="ok", message="/tmp/x"),
        PreflightCheck(name="azure_auth", status="fail", message="Run `az login`."),
        PreflightCheck(name="app_insights", status="warn", message="not configured"),
        PreflightCheck(name="foundry_project", status="skip", message="env missing"),
    ])
    text = format_report(report, color=False)
    assert "Pre-flight checks" in text
    assert "workspace" in text and "ok" in text
    assert "az login" in text  # fail rendered with humanized message
