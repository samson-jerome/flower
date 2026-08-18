from __future__ import annotations
from PySide6.QtCore import QSettings

_SETTINGS_KEY = "editor/indent_width"

DEFAULT_INDENT_WIDTH = 4
MIN_INDENT_WIDTH = 1
MAX_INDENT_WIDTH = 8


def load_indent_width() -> int:
    """How many spaces one Tab keystroke inserts in a code field.

    Anything that isn't an integer within the bounds falls back to the
    default: QSettings reads an ini file back as strings, and the value ends
    up multiplying a string, where a bad one would raise or hang the editor
    on an absurd width."""
    value = QSettings().value(_SETTINGS_KEY, DEFAULT_INDENT_WIDTH)
    try:
        width = int(value)
    except (TypeError, ValueError):
        return DEFAULT_INDENT_WIDTH
    if not MIN_INDENT_WIDTH <= width <= MAX_INDENT_WIDTH:
        return DEFAULT_INDENT_WIDTH
    return width


def save_indent_width(width: int) -> None:
    QSettings().setValue(_SETTINGS_KEY, width)
