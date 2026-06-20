"""Global workspace layout — one folder for generator, scanner, and cache."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

GENERATED_DIR_NAME = "generated"
GENERATED_FILE_NAME = "eth_addrs.jsonl"
FOUND_DIR_NAME = "found_wallets"
CACHE_FILE_NAME = "checked_cache.json"
SETTINGS_ORG = "ethereum-vanity"
SETTINGS_APP = "Ethereum Vanity"


def default_workspace() -> Path:
    return Path.home() / "ethereum-vanity"


@dataclass(frozen=True)
class WorkspaceLayout:
    root: Path

    @property
    def generated_dir(self) -> Path:
        return self.root / GENERATED_DIR_NAME

    @property
    def generated_file(self) -> Path:
        return self.generated_dir / GENERATED_FILE_NAME

    @property
    def found_dir(self) -> Path:
        return self.root / FOUND_DIR_NAME

    @property
    def cache_file(self) -> Path:
        return self.root / CACHE_FILE_NAME


def workspace_layout(root: str | Path) -> WorkspaceLayout:
    return WorkspaceLayout(root=Path(root).expanduser().resolve())


def ensure_workspace(root: str | Path) -> WorkspaceLayout:
    layout = workspace_layout(root)
    layout.generated_dir.mkdir(parents=True, exist_ok=True)
    layout.found_dir.mkdir(parents=True, exist_ok=True)
    return layout


def load_saved_workspace() -> Path:
    try:
        from PySide6.QtCore import QSettings

        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        raw = settings.value("workspace", "")
        if raw:
            return Path(str(raw)).expanduser()
    except ImportError:
        pass
    return default_workspace()


def save_workspace(root: str | Path) -> None:
    try:
        from PySide6.QtCore import QSettings

        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        settings.setValue("workspace", str(Path(root).expanduser().resolve()))
    except ImportError:
        pass


def shorten_path(path: Path, *, max_len: int = 36) -> str:
    text = str(path)
    if len(text) <= max_len:
        return text
    return "…" + text[-(max_len - 1) :]
