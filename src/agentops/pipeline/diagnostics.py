"""Shared runtime diagnostics for pipeline errors."""

from __future__ import annotations


_TENANT_MISMATCH_MARKERS = (
    "Tenant provided in token does not match resource token",
    "Tenant provided in token does not match resource tenant",
    "does not match resource tenant",
)

_TENANT_MISMATCH_GUIDANCE = (
    " Check that `az login` is using the same tenant as the Foundry project, "
    "or run `az login --tenant <tenant-id>`."
)


def with_tenant_mismatch_guidance(message: str) -> str:
    """Append actionable Azure tenant guidance to matching error messages."""
    if "az login --tenant" in message:
        return message
    if any(marker in message for marker in _TENANT_MISMATCH_MARKERS):
        return f"{message}{_TENANT_MISMATCH_GUIDANCE}"
    return message
