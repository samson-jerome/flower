import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QPalette
from flower.app.prefs import theme as theme_mod
from flower.app.prefs.theme import Theme, apply_theme, load_theme, save_theme


@pytest.fixture(scope="module")
def pristine_style_and_palette(qapp):
    """Snapshot the native style/palette before any test in this module mutates it."""
    return qapp.style().objectName(), QPalette(qapp.palette())


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Redirect QSettings() to a throwaway ini file for every test in this module."""
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        theme_mod, "QSettings",
        lambda: QSettings(ini_path, QSettings.Format.IniFormat),
    )


@pytest.fixture(autouse=True)
def reset_theme_state(qapp, pristine_style_and_palette, monkeypatch):
    """Reset the shared QApplication and theme module cache to a known-clean
    state before each test, since both are process-wide singletons."""
    style_name, palette = pristine_style_and_palette
    monkeypatch.setattr(theme_mod, "_default_style_name", None)
    monkeypatch.setattr(theme_mod, "_default_palette", None)
    qapp.setStyle(style_name)
    qapp.setPalette(QPalette(palette))


def test_load_theme_defaults_to_system():
    assert load_theme() is Theme.SYSTEM


def test_save_then_load_round_trip():
    save_theme(Theme.DARK)
    assert load_theme() is Theme.DARK


def test_load_theme_ignores_corrupted_value():
    QSettings().setValue("theme", "not-a-theme")
    assert load_theme() is Theme.SYSTEM


def test_apply_dark_theme_sets_fusion_style_and_dark_palette(qapp):
    apply_theme(qapp, Theme.DARK)
    assert qapp.style().objectName().lower() == "fusion"
    assert qapp.palette().color(QPalette.ColorRole.Window).lightness() < 128


def test_apply_light_theme_sets_fusion_style_and_light_palette(qapp):
    apply_theme(qapp, Theme.LIGHT)
    assert qapp.style().objectName().lower() == "fusion"
    assert qapp.palette().color(QPalette.ColorRole.Window).lightness() >= 128


def test_apply_system_theme_restores_captured_default(qapp, pristine_style_and_palette):
    style_name, palette = pristine_style_and_palette
    apply_theme(qapp, Theme.DARK)
    apply_theme(qapp, Theme.SYSTEM)
    assert qapp.style().objectName() == style_name
    assert qapp.palette().color(QPalette.ColorRole.Window) == palette.color(QPalette.ColorRole.Window)
