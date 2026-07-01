import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QDialog, QPushButton
from flower.ui import theme as theme_mod
from flower.ui.theme import Theme, load_theme, save_theme
from flower.ui.preferences_dialog import PreferencesDialog


@pytest.fixture(scope="module")
def pristine_style_and_palette(qapp):
    return qapp.style().objectName(), QPalette(qapp.palette())


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        theme_mod, "QSettings",
        lambda: QSettings(ini_path, QSettings.Format.IniFormat),
    )


@pytest.fixture(autouse=True)
def reset_theme_state(qapp, pristine_style_and_palette, monkeypatch):
    style_name, palette = pristine_style_and_palette
    monkeypatch.setattr(theme_mod, "_default_style_name", None)
    monkeypatch.setattr(theme_mod, "_default_palette", None)
    qapp.setStyle(style_name)
    qapp.setPalette(QPalette(palette))


def test_dialog_preselects_current_theme(qapp):
    save_theme(Theme.DARK)
    dialog = PreferencesDialog()
    assert dialog._radios[Theme.DARK].isChecked()
    assert not dialog._radios[Theme.LIGHT].isChecked()
    assert not dialog._radios[Theme.SYSTEM].isChecked()


def test_selecting_a_radio_saves_and_applies_theme(qapp):
    dialog = PreferencesDialog()
    dialog._radios[Theme.DARK].setChecked(True)
    assert load_theme() is Theme.DARK
    assert qapp.style().objectName().lower() == "fusion"
    assert qapp.palette().color(QPalette.ColorRole.Window).lightness() < 128


def test_close_button_accepts_dialog(qapp):
    dialog = PreferencesDialog()
    finished = []
    dialog.finished.connect(finished.append)
    close_btn = dialog.findChild(QPushButton)
    close_btn.click()
    assert finished == [QDialog.DialogCode.Accepted]
