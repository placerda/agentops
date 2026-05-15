"""Pre-flight checks shared by `agentops doctor`, `agentops dashboard`,
and `agentops agent serve`.

Goal: surface every reason the agent might silently misbehave *before*
the user waits ~20 seconds for the first dashboard render or the first
doctor run, and tell them exactly what to fix.

The checks are intentionally fast and best-effort:

* No retries — a single shot with the standard 30-second
  ``DefaultAzureCredential(process_timeout=30)`` timeout.
* Failures never raise into the CLI; they return a status row.
* Optional checks (Foundry / App Insights / ARM) are skipped cleanly
  when the relevant env var or config is absent.

Callers receive a list of :class:`PreflightCheck` rows and decide what
to do with them. The default policy is *advisory* — print warnings and
continue. Strict CI pipelines can pass ``--strict-preflight`` to make
the CLI exit non-zero on any failure.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional

log = logging.getLogger(__name__)


_Status = Literal["ok", "warn", "skip", "fail"]


@dataclass(frozen=True)
class PreflightCheck:
    """One row in the pre-flight summary."""

    name: str
    status: _Status
    message: str
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class PreflightReport:
    """Aggregate result of a pre-flight run."""

    checks: List[PreflightCheck]

    @property
    def has_failures(self) -> bool:
        return any(c.status == "fail" for c in self.checks)

    @property
    def has_warnings(self) -> bool:
        return any(c.status == "warn" for c in self.checks)


_AZURE_RM_SCOPE = "https://management.azure.com/.default"


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_workspace(workspace: Path) -> PreflightCheck:
    """The workspace must exist and contain `.agentops/`."""
    started = time.time()
    if not workspace.exists() or not workspace.is_dir():
        return PreflightCheck(
            name="workspace",
            status="fail",
            message=f"Workspace path does not exist: {workspace}",
            duration_seconds=time.time() - started,
        )
    agentops_dir = workspace / ".agentops"
    if not agentops_dir.is_dir():
        return PreflightCheck(
            name="workspace",
            status="warn",
            message=(
                "No `.agentops/` directory in the workspace. Run "
                "`agentops init` to scaffold it; otherwise checks "
                "that depend on workspace files will be silent."
            ),
            duration_seconds=time.time() - started,
        )
    return PreflightCheck(
        name="workspace",
        status="ok",
        message=f"{workspace}",
        duration_seconds=time.time() - started,
    )


def _check_azure_cli() -> PreflightCheck:
    """`DefaultAzureCredential` can acquire an ARM token.

    On a dev box this is shorthand for "`az login` is current"; on a
    CI runner it covers any of the workload-identity / managed-identity
    sub-credentials.
    """
    started = time.time()
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError:
        return PreflightCheck(
            name="azure_auth",
            status="skip",
            message=(
                "azure-identity not installed. Install the agent "
                "extra: `pip install agentops-toolkit[agent]`."
            ),
            duration_seconds=time.time() - started,
        )
    try:
        cred = DefaultAzureCredential(
            exclude_developer_cli_credential=True, process_timeout=30
        )
        token = cred.get_token(_AZURE_RM_SCOPE)
    except Exception as exc:  # noqa: BLE001
        # Humanize the wall-of-text DefaultAzureCredential failure.
        text = str(exc).lower()
        if (
            "azureclicredential: failed to invoke the azure cli" in text
            or "no accounts were found in the cache" in text
        ):
            msg = (
                "Not signed in to Azure. Run `az login` in this shell "
                "and re-run the command."
            )
        else:
            snippet = str(exc).splitlines()[0][:200]
            msg = f"DefaultAzureCredential failed: {snippet}"
        return PreflightCheck(
            name="azure_auth",
            status="fail",
            message=msg,
            duration_seconds=time.time() - started,
        )
    expires_in = int(token.expires_on - time.time())
    return PreflightCheck(
        name="azure_auth",
        status="ok",
        message=f"ARM token acquired (expires in {expires_in // 60} min)",
        duration_seconds=time.time() - started,
    )


def _check_foundry_project() -> PreflightCheck:
    """`AZURE_AI_FOUNDRY_PROJECT_ENDPOINT` reachable + App Insights wired.

    Reuses the cached discovery helper so a second call inside the same
    process is free.
    """
    started = time.time()
    endpoint = os.getenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        return PreflightCheck(
            name="foundry_project",
            status="skip",
            message=(
                "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT is not set; "
                "Foundry-control plane checks will be skipped."
            ),
            duration_seconds=time.time() - started,
        )
    try:
        from agentops.utils.foundry_discovery import (
            resolve_appinsights_connection_with_reason,
        )
    except ImportError:
        return PreflightCheck(
            name="foundry_project",
            status="skip",
            message="agentops.utils.foundry_discovery not available",
            duration_seconds=time.time() - started,
        )
    conn, reason = resolve_appinsights_connection_with_reason(endpoint)
    if conn:
        return PreflightCheck(
            name="foundry_project",
            status="ok",
            message="Foundry project reachable; App Insights connection auto-discovered",
            duration_seconds=time.time() - started,
        )
    return PreflightCheck(
        name="foundry_project",
        status="warn",
        message=f"Foundry discovery failed: {reason}",
        duration_seconds=time.time() - started,
    )


def _check_application_insights_env() -> PreflightCheck:
    """Heads-up when neither env var nor Foundry discovery yields a
    connection string. The production telemetry tile will stay grey."""
    started = time.time()
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING") or os.getenv(
        "AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING"
    ):
        return PreflightCheck(
            name="app_insights",
            status="ok",
            message="APPLICATIONINSIGHTS_CONNECTION_STRING is set",
            duration_seconds=time.time() - started,
        )
    # Try Foundry discovery as a fallback (uses the same cached helper).
    endpoint = os.getenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT")
    if endpoint:
        try:
            from agentops.utils.foundry_discovery import (
                resolve_appinsights_connection_with_reason,
            )
            conn, _ = resolve_appinsights_connection_with_reason(endpoint)
            if conn:
                return PreflightCheck(
                    name="app_insights",
                    status="ok",
                    message="App Insights resolved via Foundry discovery",
                    duration_seconds=time.time() - started,
                )
        except ImportError:
            pass
    return PreflightCheck(
        name="app_insights",
        status="warn",
        message=(
            "No App Insights connection found. Production telemetry "
            "will be empty. Set APPLICATIONINSIGHTS_CONNECTION_STRING "
            "or wire App Insights to your Foundry project."
        ),
        duration_seconds=time.time() - started,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


_Scope = Literal["doctor", "dashboard", "agent_serve"]


def run_preflight(
    workspace: Path,
    *,
    scope: _Scope = "doctor",
) -> PreflightReport:
    """Run every check applicable to ``scope`` and return the report."""
    checks: List[PreflightCheck] = []

    checks.append(_check_workspace(workspace))

    # Auth is needed by every scope that talks to Azure.
    checks.append(_check_azure_cli())

    # Foundry / App Insights probes are advisory; they help the user
    # understand *why* certain sources will be silent rather than
    # blocking the run.
    checks.append(_check_foundry_project())
    checks.append(_check_application_insights_env())

    return PreflightReport(checks=checks)


def format_report(report: PreflightReport, *, color: bool = True) -> str:
    """Render the report as a short multi-line summary."""
    icon = {
        "ok":   ("\u2713", "32"),  # green check
        "warn": ("!",      "33"),  # yellow bang
        "skip": ("-",      "37"),  # grey dash
        "fail": ("\u00d7", "31"),  # red cross
    }
    lines = ["Pre-flight checks:"]
    for c in report.checks:
        glyph, ansi = icon.get(c.status, ("?", "0"))
        if color:
            label = f"\x1b[{ansi}m{glyph} {c.status:<4}\x1b[0m"
        else:
            label = f"{glyph} {c.status:<4}"
        lines.append(f"  {label}  {c.name:<18} {c.message}")
    return "\n".join(lines)
