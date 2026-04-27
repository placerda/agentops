"""Workspace initialization service for `agentops init`."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Dict, List


@dataclass
class InitResult:
    workspace_dir: Path
    created_dirs: List[Path] = field(default_factory=list)
    created_files: List[Path] = field(default_factory=list)
    overwritten_files: List[Path] = field(default_factory=list)
    skipped_files: List[Path] = field(default_factory=list)


_TEMPLATE_PACKAGE = "agentops.templates"
_TEMPLATE_FILES: tuple[str, ...] = (
    "config.yaml",
    "run.yaml",
    "run-rag.yaml",
    "run-agent.yaml",
    "run-agent-local.yaml",
    "run-http-model.yaml",
    "run-http-rag.yaml",
    "run-http-agent-tools.yaml",
    "run-callable.yaml",
    "callable_adapter.py",
    "agent_framework_adapter.py",
    "multi_agent_workflow.py",
    ".gitignore",
    "bundles/model_quality_baseline.yaml",
    "bundles/rag_quality_baseline.yaml",
    "bundles/conversational_agent_baseline.yaml",
    "bundles/agent_workflow_baseline.yaml",
    "bundles/safe_agent_baseline.yaml",
    "datasets/smoke-model-direct.yaml",
    "datasets/smoke-rag.yaml",
    "datasets/smoke-agent-tools.yaml",
    "datasets/smoke-conversational.yaml",
    "data/smoke-model-direct.jsonl",
    "data/smoke-rag.jsonl",
    "data/smoke-agent-tools.jsonl",
    "data/smoke-conversational.jsonl",
    "workflows/agentops-eval.yml",
)


def _load_seed_templates() -> Dict[str, str]:
    """Load workspace seed files from packaged template assets."""
    templates_root = files(_TEMPLATE_PACKAGE)
    loaded: Dict[str, str] = {}

    for relative_path in _TEMPLATE_FILES:
        template = templates_root.joinpath(relative_path)
        loaded[relative_path] = template.read_text(encoding="utf-8")

    return loaded


def initialize_workspace(directory: Path, force: bool = False) -> InitResult:
    workspace_root = directory.resolve()
    agentops_dir = workspace_root / ".agentops"

    result = InitResult(workspace_dir=agentops_dir)

    folders = [
        agentops_dir,
        agentops_dir / "bundles",
        agentops_dir / "datasets",
        agentops_dir / "data",
        agentops_dir / "results",
    ]

    for folder in folders:
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
            result.created_dirs.append(folder)

    for relative_path, content in _load_seed_templates().items():
        file_path = agentops_dir / relative_path
        existed_before = file_path.exists()
        if existed_before and not force:
            result.skipped_files.append(file_path)
            continue

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        if existed_before:
            result.overwritten_files.append(file_path)
        else:
            result.created_files.append(file_path)

    return result


# ---------------------------------------------------------------------------
# 1.0 flat workspace (agentops.yaml at project root + minimal seed dataset)
# ---------------------------------------------------------------------------


_FLAT_FILES: Dict[str, str] = {
    "agentops.yaml": "agentops.yaml",
    ".agentops/data/smoke.jsonl": "smoke.jsonl",
}


def initialize_flat_workspace(directory: Path, force: bool = False) -> InitResult:
    """Bootstrap the AgentOps 1.0 workspace.

    Creates ``agentops.yaml`` at the project root and a tiny seed dataset at
    ``.agentops/data/smoke.jsonl``. This is the recommended starting point for
    new projects; the legacy multi-file workspace remains available via
    :func:`initialize_workspace`.
    """
    project_root = directory.resolve()
    result = InitResult(workspace_dir=project_root / ".agentops")

    templates_root = files(_TEMPLATE_PACKAGE)
    for relative_path, template_name in _FLAT_FILES.items():
        target = project_root / relative_path
        existed_before = target.exists()
        if existed_before and not force:
            result.skipped_files.append(target)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.parent.exists():
            result.created_dirs.append(target.parent)

        content = templates_root.joinpath(template_name).read_text(encoding="utf-8")
        target.write_text(content, encoding="utf-8")

        if existed_before:
            result.overwritten_files.append(target)
        else:
            result.created_files.append(target)

    return result
