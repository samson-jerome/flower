from __future__ import annotations
from enum import Enum
from PySide6.QtCore import QSettings
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

_SETTINGS_KEY = "theme"

# Style/palette captured on first use, before any theme override is applied,
# so "Système" can restore exactly what the platform gave us at startup.
_default_style_name: str | None = None
_default_palette: QPalette | None = None


class Theme(str, Enum):
    LIGHT  = "light"
    DARK   = "dark"
    SYSTEM = "system"


def load_theme() -> Theme:
    value = QSettings().value(_SETTINGS_KEY, Theme.SYSTEM.value)
    try:
        return Theme(value)
    except ValueError:
        return Theme.SYSTEM


def save_theme(theme: Theme) -> None:
    QSettings().setValue(_SETTINGS_KEY, theme.value)


def _dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.Base,             QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase,    QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase,      QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ToolTipText,      QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.Text,             QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.Button,           QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText,       QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.BrightText,       QColor(255, 60, 60))
    palette.setColor(QPalette.ColorRole.Link,             QColor(90, 160, 230))
    palette.setColor(QPalette.ColorRole.Highlight,        QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText,  QColor(35, 35, 35))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,        QColor(127, 127, 127))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText,  QColor(127, 127, 127))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText,  QColor(127, 127, 127))
    return palette


def _capture_defaults(app: QApplication) -> None:
    global _default_style_name, _default_palette
    if _default_style_name is None:
        _default_style_name = app.style().objectName()
        _default_palette = QPalette(app.palette())


def apply_theme(app: QApplication, theme: Theme) -> None:
    """Apply `theme` to the whole application.

    SYSTEM restores the native style/palette captured at startup, which on
    modern Qt/Windows/macOS/Linux desktops already tracks the window
    manager's light/dark setting. LIGHT/DARK force the Fusion style with an
    explicit palette so the choice is independent of the OS setting.
    """
    _capture_defaults(app)
    if theme is Theme.SYSTEM:
        app.setStyle(_default_style_name)
        app.setPalette(_default_palette)
        return
    app.setStyle("Fusion")
    app.setPalette(_dark_palette() if theme is Theme.DARK else app.style().standardPalette())


def is_dark(app: QApplication) -> bool:
    """Whether the application currently renders with a dark background,
    regardless of which Theme (Light/Dark/System) produced that palette."""
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def watch_system_theme(app: QApplication) -> None:
    """React live to window-manager theme changes while Theme.SYSTEM is selected."""
    def _on_system_scheme_changed(_scheme) -> None:
        if load_theme() is Theme.SYSTEM:
            apply_theme(app, Theme.SYSTEM)
    app.styleHints().colorSchemeChanged.connect(_on_system_scheme_changed)
    # Keep the closure alive for the app's lifetime (it only holds a
    # reference through the Qt connection otherwise).
    app._theme_watcher = _on_system_scheme_changed  # type: ignore[attr-defined]
