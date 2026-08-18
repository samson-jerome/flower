from __future__ import annotations
from PySide6.QtCore import QObject, QSettings, Signal

_SETTINGS_GROUP = "highlight"

# Styles offered for each background, first entry being the default. The two
# defaults are the styles that used to be hard-coded in highlighter.py, so an
# installation with no preference set renders exactly as before.
#
# Hand-picked rather than derived from pygments.styles.get_all_styles(): the
# ~50 available styles would make for an unreadable combo box, and each entry
# here has been checked to read well against the application's own palette.
# tests/test_highlight_styles.py asserts every name still exists in Pygments.
LIGHT_STYLES = ["default", "friendly", "tango", "vs", "solarized-light"]
DARK_STYLES  = ["github-dark", "monokai", "dracula", "nord", "one-dark", "solarized-dark"]


class _Notifier(QObject):
    changed = Signal()


# Module-level singleton. QApplication.paletteChanged tells a highlighter that
# the background changed; this tells it that the *preference* changed. Both are
# needed: node editors are non-modal, so they stay visible -- and stale --
# while the preferences dialog is open.
notifier = _Notifier()


def _offered(dark: bool) -> list[str]:
    return DARK_STYLES if dark else LIGHT_STYLES


def load_style(dark: bool) -> str:
    """The style saved for this background, or its default.

    A value that isn't offered for this background falls back to the default:
    it may have been hand-edited into the settings file, saved by a version of
    the application that offered it, or belong to the other background -- a
    dark style on a light field renders dark-on-light text."""
    offered = _offered(dark)
    key = "dark" if dark else "light"
    name = QSettings().value(f"{_SETTINGS_GROUP}/{key}", offered[0])
    return name if name in offered else offered[0]


def save_style(dark: bool, name: str) -> None:
    QSettings().setValue(f"{_SETTINGS_GROUP}/{'dark' if dark else 'light'}", name)
    notifier.changed.emit()
