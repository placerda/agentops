"""Tests for ``initialize_flat_workspace``."""

from __future__ import annotations

from pathlib import Path

from agentops.services.initializer import initialize_flat_workspace


def test_creates_minimal_layout(tmp_path: Path) -> None:
    result = initialize_flat_workspace(tmp_path, force=False)

    config = tmp_path / "agentops.yaml"
    dataset = tmp_path / ".agentops" / "data" / "smoke.jsonl"

    assert config.exists()
    assert dataset.exists()
    assert config in result.created_files
    assert dataset in result.created_files
    assert "version: 1" in config.read_text(encoding="utf-8")


def test_skips_existing_files_without_force(tmp_path: Path) -> None:
    initialize_flat_workspace(tmp_path, force=False)
    config = tmp_path / "agentops.yaml"
    config.write_text("custom\n", encoding="utf-8")

    result = initialize_flat_workspace(tmp_path, force=False)

    assert config in result.skipped_files
    assert config.read_text(encoding="utf-8") == "custom\n"


def test_force_overwrites(tmp_path: Path) -> None:
    initialize_flat_workspace(tmp_path, force=False)
    config = tmp_path / "agentops.yaml"
    config.write_text("custom\n", encoding="utf-8")

    result = initialize_flat_workspace(tmp_path, force=True)

    assert config in result.overwritten_files
    assert "version: 1" in config.read_text(encoding="utf-8")
