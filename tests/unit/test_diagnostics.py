"""Tests for pipeline diagnostic helpers."""

from __future__ import annotations

from agentops.pipeline.diagnostics import with_tenant_mismatch_guidance


def test_tenant_mismatch_guidance_handles_resource_token_error():
    message = (
        "Error code: 400 - {'error': {'code': 'Tenant provided in token does "
        "not match resource token', 'message': 'Token tenant abc does not "
        "match resource tenant.'}}"
    )

    enriched = with_tenant_mismatch_guidance(message)

    assert "az login --tenant <tenant-id>" in enriched


def test_tenant_mismatch_guidance_is_idempotent():
    message = (
        "Token tenant abc does not match resource tenant. Check that `az login` "
        "is using the same tenant as the Foundry project, or run "
        "`az login --tenant <tenant-id>`."
    )

    assert with_tenant_mismatch_guidance(message) == message


def test_tenant_mismatch_guidance_leaves_unrelated_errors_unchanged():
    message = "HTTP 404 from endpoint"

    assert with_tenant_mismatch_guidance(message) == message
