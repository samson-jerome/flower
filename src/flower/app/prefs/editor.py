from __future__ import annotations
from PySide6.QtCore import QSettings
from flower.engine.execution.runner import DEFAULT_EDITOR

_SETTINGS_KEY = "editor"


def load_editor() -> str:
    """The editor command used to open the folder holding the generated
    script. A blank preference falls back to the default: an empty command
    would fail the launch with no explanation."""
    value = str(QSettings().value(_SETTINGS_KEY, DEFAULT_EDITOR) or "").strip()
    return value or DEFAULT_EDITOR


def save_editor(command: str) -> None:
    QSettings().setValue(_SETTINGS_KEY, command)
