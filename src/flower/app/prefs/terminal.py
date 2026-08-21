from __future__ import annotations
from PySide6.QtCore import QSettings
from flower.engine.execution.runner import DEFAULT_TERMINAL

_SETTINGS_KEY = "terminal"


def load_terminal() -> str:
    """The terminal command used to run a script. A blank preference falls
    back to the default: an empty command would fail the launch with no
    explanation."""
    value = str(QSettings().value(_SETTINGS_KEY, DEFAULT_TERMINAL) or "").strip()
    return value or DEFAULT_TERMINAL


def save_terminal(command: str) -> None:
    QSettings().setValue(_SETTINGS_KEY, command)
