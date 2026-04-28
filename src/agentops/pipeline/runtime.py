"""Evaluator runtime for AgentOps 1.0.

Each :class:`EvaluatorPreset` from the catalog is instantiated lazily from
``azure.ai.evaluation`` and run against one dataset row. The runtime hides
SDK details (``model_config`` for AI-assisted evaluators, ``azure_ai_project``
for safety evaluators, kwarg mapping, score extraction).
"""

from __future__ import annotations

import importlib
import inspect
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agentops.core.evaluators import EvaluatorPreset
from agentops.core.results import RowMetric

# Evaluator classes that require an evaluator model via ``model_config``.
_AI_ASSISTED = {
    "GroundednessEvaluator",
    "RelevanceEvaluator",
    "CoherenceEvaluator",
    "FluencyEvaluator",
    "SimilarityEvaluator",
    "RetrievalEvaluator",
    "ResponseCompletenessEvaluator",
    "QAEvaluator",
    "IntentResolutionEvaluator",
    "TaskAdherenceEvaluator",
    "ToolCallAccuracyEvaluator",
}

# Evaluator classes that require ``azure_ai_project``.
_SAFETY = {
    "ViolenceEvaluator",
    "SexualEvaluator",
    "SelfHarmEvaluator",
    "HateUnfairnessEvaluator",
    "ContentSafetyEvaluator",
    "ProtectedMaterialEvaluator",
}


@dataclass
class EvaluatorRuntime:
    """A loaded, ready-to-call evaluator."""

    preset: EvaluatorPreset
    callable: Any  # evaluator instance or sentinel for "latency"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _credential() -> Any:
    from azure.identity import DefaultAzureCredential  # noqa: WPS433

    return DefaultAzureCredential(exclude_developer_cli_credential=True)


def _model_config() -> Dict[str, str]:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT") or os.getenv(
        "AZURE_AI_MODEL_DEPLOYMENT_NAME"
    )
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")

    missing = []
    if not endpoint:
        missing.append("AZURE_OPENAI_ENDPOINT")
    if not deployment:
        missing.append("AZURE_OPENAI_DEPLOYMENT")
    if missing:
        raise RuntimeError(
            "AI-assisted evaluators require an evaluator model. "
            "Missing environment variables: " + ", ".join(missing)
        )

    config: Dict[str, str] = {
        "azure_endpoint": endpoint,  # type: ignore[dict-item]
        "azure_deployment": deployment,  # type: ignore[dict-item]
    }
    if api_version:
        config["api_version"] = api_version
    return config


def _project_endpoint() -> str:
    endpoint = os.getenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "Safety evaluators require AZURE_AI_FOUNDRY_PROJECT_ENDPOINT."
        )
    return endpoint


_LATENCY_SENTINEL = object()


def load_evaluator(preset: EvaluatorPreset) -> EvaluatorRuntime:
    """Instantiate one evaluator. Raises a clear error if the SDK is missing."""
    if preset.class_name == "_latency":
        return EvaluatorRuntime(preset=preset, callable=_LATENCY_SENTINEL)

    try:
        module = importlib.import_module("azure.ai.evaluation")
    except ImportError as exc:
        raise RuntimeError(
            "Evaluators require the 'azure-ai-evaluation' package. "
            "Install with: pip install azure-ai-evaluation"
        ) from exc

    cls = getattr(module, preset.class_name, None)
    if cls is None:
        raise RuntimeError(
            f"Evaluator class {preset.class_name!r} not found in azure.ai.evaluation"
        )

    init_kwargs: Dict[str, Any] = {}
    if preset.class_name in _AI_ASSISTED:
        init_kwargs["model_config"] = _model_config()
    if preset.class_name in _SAFETY:
        init_kwargs["azure_ai_project"] = _project_endpoint()
        init_kwargs["credential"] = _credential()

    try:
        instance = cls(**init_kwargs) if inspect.isclass(cls) else cls
    except TypeError:
        # Some evaluators reject unexpected kwargs (e.g. F1ScoreEvaluator).
        instance = cls() if inspect.isclass(cls) else cls

    return EvaluatorRuntime(preset=preset, callable=instance)


def load_evaluators(presets: List[EvaluatorPreset]) -> List[EvaluatorRuntime]:
    return [load_evaluator(preset) for preset in presets]


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


_PLACEHOLDERS = {
    "$prompt": "input",
    "$prediction": "response",
    "$expected": "expected",
    "$context": "context",
    "$tool_calls": "tool_calls",
    "$tool_definitions": "tool_definitions",
}


def _resolve_kwargs(
    mapping: Dict[str, str],
    *,
    row: Dict[str, Any],
    response: str,
) -> Dict[str, Any]:
    resolved: Dict[str, Any] = {}
    merged = {**row, "response": response, "input": row.get("input")}
    for kwarg, placeholder in mapping.items():
        if not isinstance(placeholder, str) or not placeholder.startswith("$"):
            resolved[kwarg] = placeholder
            continue
        source_key = _PLACEHOLDERS.get(placeholder)
        if source_key is None:
            raise ValueError(f"unknown evaluator placeholder {placeholder!r}")
        value = merged.get(source_key)
        if value is None:
            continue
        resolved[kwarg] = value
    return resolved


def _extract_score(payload: Any, score_key: str) -> Optional[float]:
    if payload is None:
        return None
    if isinstance(payload, (int, float)):
        return float(payload)
    if not isinstance(payload, dict):
        return None
    for candidate in (
        score_key,
        f"{score_key}_score",
        f"gpt_{score_key}",
        "score",
    ):
        value = payload.get(candidate)
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            return float(value)
    return None


def run_evaluator(
    runtime: EvaluatorRuntime,
    *,
    row: Dict[str, Any],
    response: str,
    latency_seconds: float,
) -> RowMetric:
    """Execute one evaluator on one row. Captures errors so the run continues."""
    preset = runtime.preset
    if runtime.callable is _LATENCY_SENTINEL:
        return RowMetric(name=preset.score_key, value=float(latency_seconds))

    try:
        kwargs = _resolve_kwargs(preset.input_mapping, row=row, response=response)
        result = runtime.callable(**kwargs)
        score = _extract_score(result, preset.score_key)
        return RowMetric(name=preset.score_key, value=score)
    except Exception as exc:  # noqa: BLE001
        return RowMetric(name=preset.score_key, error=str(exc))
