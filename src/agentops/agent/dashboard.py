"""Local web dashboard for the AgentOps watchdog agent.

``agentops monitor`` boots a tiny FastAPI server that reads the
analysis history from ``.agentops/agent/history.jsonl`` and serves a
single dashboard page in a FitBit-inspired dark theme. No external
frontend dependencies (sparklines are inline SVG); no Azure resource
required.

The server is intentionally read-only and bound to ``127.0.0.1`` by
default — it is a developer-tool surface, not a production service.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from agentops.agent.history import AnalysisRecord, load_analysis_history


# ---------------------------------------------------------------------------
# Data shaping for the dashboard
# ---------------------------------------------------------------------------


_CATEGORY_LABELS = {
    "quality": "Quality",
    "performance": "Performance",
    "reliability": "Reliability",
    "security": "Security",
}

_BADGE_FOR_SEVERITY = {
    None: ("in range", "ok"),
    "info": ("info", "info"),
    "warning": ("warnings", "warn"),
    "critical": ("critical", "crit"),
}


def build_dashboard_payload(
    workspace: Path,
    *,
    history: Optional[List[AnalysisRecord]] = None,
) -> Dict[str, Any]:
    """Reduce raw analysis history into a dashboard-ready dict.

    Exposed as a pure function so it can be exercised by tests without
    spinning up the HTTP server.
    """
    records = history if history is not None else load_analysis_history(workspace)
    latest = records[-1] if records else None

    def _series(extractor) -> List[float]:
        return [float(extractor(r) or 0) for r in records]

    findings_series = _series(lambda r: r.findings_total)
    critical_series = _series(lambda r: r.findings_by_severity.get("critical", 0))

    category_cards: List[Dict[str, Any]] = []
    for key, label in _CATEGORY_LABELS.items():
        series = _series(lambda r, k=key: r.findings_by_category.get(k, 0))
        current = int(series[-1]) if series else 0
        category_cards.append({
            "key": key,
            "label": label,
            "current": current,
            "series": series,
            "badge": _category_badge(key, current, records),
        })

    latest_label, latest_badge = _latest_run_badge(latest)

    return {
        "has_history": bool(records),
        "history_count": len(records),
        "workspace": str(workspace.resolve()),
        "headline_cards": [
            {
                "key": "findings_total",
                "label": "Findings",
                "value": int(findings_series[-1]) if findings_series else 0,
                "unit": "total",
                "series": findings_series,
                "badge": _headline_badge_total(findings_series),
            },
            {
                "key": "critical",
                "label": "Critical",
                "value": int(critical_series[-1]) if critical_series else 0,
                "unit": "open",
                "series": critical_series,
                "badge": _headline_badge_critical(critical_series),
            },
        ],
        "category_cards": category_cards,
        "latest_run": {
            "label": latest_label,
            "badge": latest_badge,
            "timestamp": latest.timestamp if latest else None,
            "max_severity": latest.max_severity if latest else None,
            "duration_seconds": latest.duration_seconds if latest else None,
            "sources_enabled": latest.sources_enabled if latest else [],
        },
    }


def _headline_badge_total(series: List[float]) -> Dict[str, str]:
    if not series:
        return {"label": "no data", "tone": "muted"}
    last = series[-1]
    if last == 0:
        return {"label": "all clear", "tone": "ok"}
    if len(series) >= 2 and last > series[-2]:
        return {"label": "trending up", "tone": "warn"}
    return {"label": "open", "tone": "info"}


def _headline_badge_critical(series: List[float]) -> Dict[str, str]:
    if not series:
        return {"label": "no data", "tone": "muted"}
    last = series[-1]
    if last == 0:
        return {"label": "none", "tone": "ok"}
    return {"label": "above zero", "tone": "crit"}


def _category_badge(
    key: str, current: int, records: List[AnalysisRecord]
) -> Dict[str, str]:
    if not records:
        return {"label": "no data", "tone": "muted"}
    if current == 0:
        return {"label": "in range", "tone": "ok"}
    # If the previous analysis was zero and the current is non-zero,
    # surface as regression.
    if len(records) >= 2:
        prev = records[-2].findings_by_category.get(key, 0)
        if prev == 0:
            return {"label": "new", "tone": "warn"}
        if current > prev:
            return {"label": "trending up", "tone": "warn"}
        if current < prev:
            return {"label": "trending down", "tone": "ok"}
    return {"label": "active", "tone": "info"}


def _latest_run_badge(record: Optional[AnalysisRecord]) -> tuple:
    if record is None:
        return ("never", {"label": "no data", "tone": "muted"})
    label, tone = _BADGE_FOR_SEVERITY[record.max_severity]
    return (
        f"{record.findings_total} finding(s)",
        {"label": label, "tone": tone},
    )


# ---------------------------------------------------------------------------
# HTML rendering — inline, zero JS deps
# ---------------------------------------------------------------------------


def render_dashboard_html(payload: Dict[str, Any]) -> str:
    """Render the dashboard page from a payload built by
    :func:`build_dashboard_payload`. Returns a complete HTML document.
    """
    headline_html = "".join(_render_card(card, hero=True) for card in payload["headline_cards"])
    category_html = "".join(_render_card(card) for card in payload["category_cards"])
    latest = payload["latest_run"]
    latest_html = _render_latest_card(latest)

    empty_state = ""
    if not payload["has_history"]:
        empty_state = (
            '<div class="empty-state">'
            "No analysis history yet — run "
            "<code>agentops agent analyze</code> "
            "to populate this dashboard."
            "</div>"
        )

    return _DASHBOARD_TEMPLATE.format(
        headline_cards=headline_html,
        category_cards=category_html,
        latest_card=latest_html,
        empty_state=empty_state,
        history_count=payload["history_count"],
        workspace=payload["workspace"],
    )


def _render_card(card: Dict[str, Any], *, hero: bool = False) -> str:
    spark = _sparkline_svg(card["series"])
    badge = card["badge"]
    css_class = "card hero" if hero else "card"
    value = card.get("value", card.get("current", 0))
    unit = card.get("unit", "")
    unit_html = f'<span class="card-unit"> {unit}</span>' if unit else ""
    return (
        f'<div class="{css_class}">'
        f'<div class="card-label">{card["label"]}</div>'
        f'<div class="card-value">{value}{unit_html}</div>'
        f"{spark}"
        f'<div class="badge tone-{badge["tone"]}">{badge["label"]}</div>'
        f"</div>"
    )


def _render_latest_card(latest: Dict[str, Any]) -> str:
    badge = latest["badge"]
    if latest["timestamp"]:
        ts = latest["timestamp"]
        sources = ", ".join(latest.get("sources_enabled") or []) or "—"
        duration = (
            f"{latest['duration_seconds']:.1f}s"
            if latest.get("duration_seconds") is not None
            else "—"
        )
        body = (
            f'<div class="card-label">Last analysis</div>'
            f'<div class="card-value">{latest["label"]}</div>'
            f'<div class="card-meta">'
            f"<span>{ts}</span>"
            f"<span>duration: {duration}</span>"
            f"<span>sources: {sources}</span>"
            f"</div>"
            f'<div class="badge tone-{badge["tone"]}">{badge["label"]}</div>'
        )
    else:
        body = (
            f'<div class="card-label">Last analysis</div>'
            f'<div class="card-value">never</div>'
            f'<div class="badge tone-{badge["tone"]}">{badge["label"]}</div>'
        )
    return f'<div class="card hero">{body}</div>'


def _sparkline_svg(series: List[float]) -> str:
    """Render a minimalistic 7-point sparkline as inline SVG."""
    if not series:
        return ""
    window = series[-12:]
    if len(window) == 1:
        window = [window[0], window[0]]
    width = 240
    height = 56
    pad = 4
    max_v = max(window) or 1.0
    min_v = min(window)
    span = max(max_v - min_v, 1.0)
    step = (width - 2 * pad) / (len(window) - 1) if len(window) > 1 else 0
    points = []
    for i, v in enumerate(window):
        x = pad + i * step
        y = height - pad - ((v - min_v) / span) * (height - 2 * pad)
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    last_x = pad + (len(window) - 1) * step
    last_y = (
        height
        - pad
        - ((window[-1] - min_v) / span) * (height - 2 * pad)
    )
    return (
        f'<svg class="sparkline" viewBox="0 0 {width} {height}" preserveAspectRatio="none">'
        f'<polyline fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{polyline}"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3" fill="currentColor"/>'
        f"</svg>"
    )


_DASHBOARD_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>AgentOps Monitor</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta http-equiv="refresh" content="15" />
<style>
  :root {{
    --bg: #0a0a0a;
    --card: #161616;
    --border: #1f1f1f;
    --text: #f4f4f5;
    --text-dim: #a1a1aa;
    --ok: #4ade80;
    --info: #38bdf8;
    --warn: #fbbf24;
    --crit: #f87171;
    --muted: #52525b;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
  }}
  header {{
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 24px;
  }}
  header h1 {{
    margin: 0; font-size: 20px; font-weight: 600; letter-spacing: 0.02em;
  }}
  header .subtitle {{ color: var(--text-dim); font-size: 13px; }}
  .section-title {{
    margin: 24px 0 12px; font-size: 15px; font-weight: 600;
    color: var(--text); letter-spacing: 0.01em;
  }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 16px;
  }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 20px;
    display: flex; flex-direction: column; gap: 8px;
    color: var(--text);
  }}
  .card.hero {{ background: linear-gradient(160deg, #181818 0%, #121212 100%); }}
  .card-label {{ color: var(--text-dim); font-size: 13px; font-weight: 500; }}
  .card-value {{
    font-size: 40px; font-weight: 600; line-height: 1.1;
    margin: 4px 0 0;
  }}
  .card-unit {{ color: var(--text-dim); font-size: 14px; font-weight: 500; margin-left: 6px; }}
  .card-meta {{
    display: flex; flex-direction: column; gap: 2px;
    color: var(--text-dim); font-size: 12px; margin-top: 4px;
  }}
  .sparkline {{ width: 100%; height: 56px; color: var(--ok); margin-top: 4px; }}
  .card.hero .sparkline {{ color: var(--info); }}
  .badge {{
    display: inline-flex; align-self: flex-start; align-items: center;
    padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600;
    text-transform: lowercase; margin-top: 6px;
  }}
  .tone-ok    {{ background: rgba(74, 222, 128, 0.12); color: var(--ok); }}
  .tone-info  {{ background: rgba(56, 189, 248, 0.12); color: var(--info); }}
  .tone-warn  {{ background: rgba(251, 191, 36, 0.12); color: var(--warn); }}
  .tone-crit  {{ background: rgba(248, 113, 113, 0.12); color: var(--crit); }}
  .tone-muted {{ background: rgba(82, 82, 91, 0.20); color: var(--muted); }}
  .empty-state {{
    background: var(--card); border: 1px dashed var(--border);
    border-radius: 16px; padding: 24px; text-align: center;
    color: var(--text-dim); margin: 24px 0;
  }}
  .empty-state code {{
    background: #1f1f1f; padding: 2px 6px; border-radius: 6px;
    color: var(--text);
  }}
  footer {{
    margin-top: 32px; font-size: 12px; color: var(--text-dim);
    text-align: center;
  }}
</style>
</head>
<body>
<header>
  <div>
    <h1>AgentOps monitor</h1>
    <div class="subtitle">{workspace}</div>
  </div>
  <div class="subtitle">{history_count} analysis run(s)</div>
</header>

{empty_state}

<div class="section-title">Key metrics</div>
<div class="grid">{headline_cards}{latest_card}</div>

<div class="section-title">By category</div>
<div class="grid">{category_cards}</div>

<footer>Auto-refreshes every 15s · agentops monitor</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


def create_app(workspace: Path):
    """Return a FastAPI app rooted at *workspace*."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "agentops monitor requires the [agent] extra. "
            "Install with: pip install 'agentops-toolkit[agent]'"
        ) from exc

    app = FastAPI(title="AgentOps Monitor", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def _index() -> HTMLResponse:
        payload = build_dashboard_payload(workspace)
        return HTMLResponse(render_dashboard_html(payload))

    @app.get("/api/history")
    def _api_history(limit: Optional[int] = None) -> JSONResponse:
        records = load_analysis_history(workspace, limit=limit)
        return JSONResponse([r.to_dict() for r in records])

    @app.get("/healthz")
    def _healthz() -> Dict[str, str]:
        return {"status": "ok"}

    return app
