"""Resolve application icon paths for Qt and desktop integration."""

from __future__ import annotations

from pathlib import Path


def _icon_candidates() -> list[Path]:
    here = Path(__file__).resolve()
    project_root = here.parents[2]
    return [
        Path("/usr/share/icons/hicolor/scalable/apps/ethereum-vanity.svg"),
        Path("/usr/share/pixmaps/ethereum-vanity.svg"),
        project_root / "debian" / "icons" / "ethereum-vanity.svg",
    ]


def find_app_icon_path() -> Path | None:
    for path in _icon_candidates():
        if path.is_file():
            return path
    return None
