"""MLOps check — pipeline / config hygiene findings.

These rules read the eval workspace (``agentops.yaml`` + ``.agentops/``
+ ``.github/workflows/``) and flag GenAIOps practice gaps that aren't
covered by Foundry's Operate -> Compliance surface. Examples:

* Agent string isn't pinned to a version (``my-agent`` instead of
  ``my-agent:3``).
* ``agentops.yaml`` ships with no ``thresholds:`` block — the gate is
  loose and depends entirely on auto-defaults.
* Repo has no ``agentops-pr.yml`` CI gate.

Findings live under :class:`Category.MLOPS` and default to
``warning`` severity unless explicitly elevated.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import yaml

from agentops.agent.findings import Category, Finding, Severity

SOURCE_NAME = "mlops_workspace"


def run_mlops_check(workspace: Path) -> List[Finding]:
    """Run all MLOps hygiene rules against ``workspace`` and return findings.

    Each rule is independent and defensive: anything it can't read is
    silently skipped so the watchdog stays useful on partial setups.
    """
    findings: List[Finding] = []

    config_path = workspace / "agentops.yaml"
    config_data = _safe_load_yaml(config_path)

    findings.extend(_check_agent_pinning(config_data))
    findings.extend(_check_thresholds_block(config_data))
    findings.extend(_check_pr_gate_workflow(workspace))

    return findings


def _check_agent_pinning(config: Optional[dict]) -> List[Finding]:
    """Warn when `agent:` is not pinned to a `:version` (foundry agent)
    or to an explicit URL/model identifier."""
    if not isinstance(config, dict):
        return []
    agent = config.get("agent")
    if not isinstance(agent, str) or not agent.strip():
        return []

    # URL targets and model: targets are inherently pinned.
    if agent.startswith("http://") or agent.startswith("https://"):
        return []
    if agent.lower().startswith("model:"):
        return []

    # For "name:version" — verify the part after ':' is non-empty and
    # not the literal "latest" alias.
    if ":" in agent:
        _, _, version = agent.partition(":")
        version = version.strip().lower()
        if version and version != "latest":
            return []

    return [
        Finding(
            id="mlops.unpinned_agent",
            severity=Severity.WARNING,
            category=Category.MLOPS,
            title="Agent target is not pinned to a version",
            summary=(
                f"`agent: {agent}` has no explicit version. CI runs will "
                "track whatever 'latest' resolves to, so a Foundry edit "
                "to the agent can change eval results without a code "
                "change in this repo."
            ),
            recommendation=(
                "Pin the agent to a published version (for example "
                "`agent: my-agent:3`). Bump the suffix deliberately when "
                "you publish a new version in Foundry."
            ),
            source=SOURCE_NAME,
            evidence={"agent": agent},
        )
    ]


def _check_thresholds_block(config: Optional[dict]) -> List[Finding]:
    """Warn when `thresholds:` is absent or empty — auto-defaults are
    fine for exploration but loose for prod gates."""
    if not isinstance(config, dict):
        return []
    thresholds = config.get("thresholds")
    if isinstance(thresholds, dict) and thresholds:
        return []
    return [
        Finding(
            id="mlops.no_thresholds",
            severity=Severity.WARNING,
            category=Category.MLOPS,
            title="agentops.yaml has no explicit thresholds",
            summary=(
                "Without a `thresholds:` block, AgentOps relies entirely "
                "on auto-defaults to decide whether a run passes or "
                "fails. That is fine for exploration but too loose for a "
                "merge gate."
            ),
            recommendation=(
                "Add a `thresholds:` map to `agentops.yaml` listing the "
                "specific metric floors/ceilings your team agrees on "
                "(e.g. `coherence: \">=3\"`, `avg_latency_seconds: "
                "\"<=30\"`)."
            ),
            source=SOURCE_NAME,
        )
    ]


def _check_pr_gate_workflow(workspace: Path) -> List[Finding]:
    """Warn when the repo has no `agentops-pr.yml` CI gate."""
    candidate = workspace / ".github" / "workflows" / "agentops-pr.yml"
    if candidate.exists():
        return []
    # If there's no .github/workflows directory at all, the repo may not
    # be a CI-driven project — only warn when there *is* a workflows dir
    # so we don't pester e.g. local-only sandboxes.
    if not (workspace / ".github" / "workflows").is_dir():
        return []
    return [
        Finding(
            id="mlops.no_pr_gate",
            severity=Severity.WARNING,
            category=Category.MLOPS,
            title="Repository has no AgentOps PR gate",
            summary=(
                "There is a `.github/workflows/` directory but no "
                "`agentops-pr.yml`. PRs can merge without running an "
                "AgentOps evaluation, so quality regressions slip "
                "through unchecked."
            ),
            recommendation=(
                "Run `agentops workflow generate` to scaffold the PR "
                "gate + deploy templates, commit the result, and require "
                "the AgentOps PR check on your default branch under "
                "Settings -> Branches."
            ),
            source=SOURCE_NAME,
        )
    ]


def _safe_load_yaml(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None
