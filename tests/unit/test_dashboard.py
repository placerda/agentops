"""Tests for :mod:`agentops.agent.dashboard`."""

from __future__ import annotations

from pathlib import Path

from agentops.agent.dashboard import (
    build_dashboard_payload,
    render_dashboard_html,
)
from agentops.agent.findings import Category, Finding, Severity
from agentops.agent.history import append_analysis, build_record


def _make_history(workspace: Path, *severities_and_categories):
    """Append one record per (severity, category) tuple given."""
    for idx, (sev, cat) in enumerate(severities_and_categories):
        finding = Finding(
            id=f"f-{idx}",
            severity=sev,
            title="t",
            summary="s",
            recommendation="r",
            source="test",
            category=cat,
        )
        record = build_record(
            [finding],
            sources_enabled=["results_history"],
            lookback_days=7,
            duration_seconds=0.5,
        )
        append_analysis(workspace, record)


def test_empty_history_yields_empty_state(tmp_path: Path):
    payload = build_dashboard_payload(tmp_path)
    assert payload["has_history"] is False
    assert payload["history_count"] == 0
    html = render_dashboard_html(payload)
    assert "No analysis history yet" in html
    assert "agentops agent analyze" in html


def test_dashboard_payload_summarizes_latest_run(tmp_path: Path):
    _make_history(
        tmp_path,
        (Severity.INFO, Category.QUALITY),
        (Severity.CRITICAL, Category.SECURITY),
    )
    payload = build_dashboard_payload(tmp_path)
    assert payload["has_history"] is True
    assert payload["history_count"] == 2
    assert payload["latest_run"]["max_severity"] == "critical"
    # Headline cards present
    keys = {c["key"] for c in payload["headline_cards"]}
    assert "findings_total" in keys
    assert "critical" in keys
    # All four category cards rendered
    cat_keys = {c["key"] for c in payload["category_cards"]}
    assert cat_keys == {"quality", "performance", "reliability", "security"}


def test_dashboard_critical_badge_flags_above_zero(tmp_path: Path):
    _make_history(tmp_path, (Severity.CRITICAL, Category.SECURITY))
    payload = build_dashboard_payload(tmp_path)
    crit_card = next(c for c in payload["headline_cards"] if c["key"] == "critical")
    assert crit_card["value"] == 1
    assert crit_card["badge"]["tone"] == "crit"


def test_dashboard_html_includes_sparkline_svg(tmp_path: Path):
    for sev in (Severity.INFO, Severity.WARNING, Severity.CRITICAL):
        _make_history(tmp_path, (sev, Category.QUALITY))
    payload = build_dashboard_payload(tmp_path)
    html = render_dashboard_html(payload)
    assert "<svg" in html
    assert "polyline" in html
    assert "AgentOps monitor" in html


def test_category_badge_flags_regression(tmp_path: Path):
    # First analysis: no quality findings.
    record = build_record(
        [], sources_enabled=["results_history"], lookback_days=7, duration_seconds=0.1,
    )
    append_analysis(tmp_path, record)
    # Second analysis: one quality finding -> "new" badge.
    _make_history(tmp_path, (Severity.WARNING, Category.QUALITY))

    payload = build_dashboard_payload(tmp_path)
    quality = next(c for c in payload["category_cards"] if c["key"] == "quality")
    assert quality["current"] == 1
    assert quality["badge"]["tone"] == "warn"


def test_create_app_serves_dashboard(tmp_path: Path):
    """FastAPI integration smoke test (skipped if FastAPI not installed)."""
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        import pytest
        pytest.skip("fastapi extras not installed")

    from agentops.agent.dashboard import create_app

    _make_history(tmp_path, (Severity.INFO, Category.QUALITY))
    client = TestClient(create_app(tmp_path))

    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "AgentOps monitor" in r.text

    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    r = client.get("/api/history")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) == 1
