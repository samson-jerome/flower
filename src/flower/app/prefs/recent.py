from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import QSettings

_SETTINGS_KEY = "recentFiles"

MAX_RECENT = 20


def load_recent() -> list[str]:
    """Absolute paths, newest first. QSettings reads a one-element list back
    as a bare string, hence the isinstance check."""
    value = QSettings().value(_SETTINGS_KEY, [])
    if isinstance(value, str):
        value = [value]
    return [str(v) for v in (value or []) if v]


def _save(paths: list[str]) -> None:
    QSettings().setValue(_SETTINGS_KEY, paths)


def add_recent(path: Path) -> None:
    resolved = str(path.resolve())
    items = [x for x in load_recent() if x != resolved]
    items.insert(0, resolved)
    _save(items[:MAX_RECENT])


def remove_recent(path: Path) -> None:
    resolved = str(path.resolve())
    _save([x for x in load_recent() if x != resolved])


def clear_recent() -> None:
    _save([])
