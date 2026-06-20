"""Tests for workspace path layout."""

from pathlib import Path

from workspace import GENERATED_FILE_NAME, ensure_workspace, workspace_layout


def test_workspace_paths(tmp_path: Path) -> None:
    layout = workspace_layout(tmp_path / "eth-ws")
    assert layout.generated_file.name == GENERATED_FILE_NAME
    assert layout.found_dir.parent == layout.root


def test_ensure_workspace_creates_dirs(tmp_path: Path) -> None:
    layout = ensure_workspace(tmp_path / "ws")
    assert layout.generated_dir.is_dir()
    assert layout.found_dir.is_dir()
