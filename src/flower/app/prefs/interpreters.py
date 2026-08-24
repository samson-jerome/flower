from __future__ import annotations
from PySide6.QtCore import QSettings
from flower.engine.execution.bash_generator import DEFAULT_INTERPRETERS

_SETTINGS_GROUP = "interpreters"


def load_interpreters() -> dict[str, str]:
    settings = QSettings()
    return {
        lang: settings.value(f"{_SETTINGS_GROUP}/{lang}", default)
        for lang, default in DEFAULT_INTERPRETERS.items()
    }


def save_interpreter(language: str, command: str) -> None:
    QSettings().setValue(f"{_SETTINGS_GROUP}/{language}", command)
