import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QDialog, QPushButton
from pygments.styles import get_style_by_name
from pygments.token import Token
from flower.app import theme as theme_mod
from flower.app import interpreters as interpreters_mod
from flower.app import highlight_styles as highlight_styles_mod
from flower.app import indent as indent_mod
from flower.app.theme import Theme, load_theme, save_theme
from flower.app.interpreters import load_interpreters, save_interpreter
from flower.app.highlight_styles import DARK_STYLES, LIGHT_STYLES, load_style, save_style
from flower.app.indent import (
    MAX_INDENT_WIDTH, MIN_INDENT_WIDTH, load_indent_width, save_indent_width,
)
from flower.engine.execution.bash_generator import DEFAULT_INTERPRETERS
from flower.app.preferences_dialog import PreferencesDialog


@pytest.fixture(scope="module")
def pristine_style_and_palette(qapp):
    return qapp.style().objectName(), QPalette(qapp.palette())


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    ini_path = str(tmp_path / "settings.ini")
    settings_factory = lambda: QSettings(ini_path, QSettings.Format.IniFormat)
    monkeypatch.setattr(theme_mod, "QSettings", settings_factory)
    monkeypatch.setattr(interpreters_mod, "QSettings", settings_factory)
    monkeypatch.setattr(highlight_styles_mod, "QSettings", settings_factory)
    monkeypatch.setattr(indent_mod, "QSettings", settings_factory)


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


def test_dialog_preselects_current_interpreters(qapp):
    save_interpreter("python", "/usr/bin/python3.11")
    dialog = PreferencesDialog()
    assert dialog._interp_edits["python"].text() == "/usr/bin/python3.11"
    assert dialog._interp_edits["sh"].text() == DEFAULT_INTERPRETERS["sh"]


def test_editing_interpreter_field_saves_on_editing_finished(qapp):
    dialog = PreferencesDialog()
    dialog._interp_edits["javascript"].setText("nodejs")
    dialog._interp_edits["javascript"].editingFinished.emit()
    assert load_interpreters()["javascript"] == "nodejs"


def _keyword_color(preview):
    fmt = preview._highlighter._format_for(Token.Keyword)
    return fmt.foreground().color().name()


def _style_keyword_color(name):
    return "#" + get_style_by_name(name).style_for_token(Token.Keyword)["color"]


def test_each_combo_offers_the_styles_of_its_background(qapp):
    dialog = PreferencesDialog()
    light = [dialog._light_combo.itemText(i) for i in range(dialog._light_combo.count())]
    dark  = [dialog._dark_combo.itemText(i)  for i in range(dialog._dark_combo.count())]
    assert light == LIGHT_STYLES
    assert dark  == DARK_STYLES


def test_combos_preselect_the_saved_styles(qapp):
    save_style(dark=False, name="tango")
    save_style(dark=True,  name="dracula")
    dialog = PreferencesDialog()
    assert dialog._light_combo.currentText() == "tango"
    assert dialog._dark_combo.currentText()  == "dracula"


def test_choosing_a_style_saves_it(qapp):
    dialog = PreferencesDialog()
    dialog._dark_combo.setCurrentText("monokai")
    assert load_style(dark=True) == "monokai"
    assert load_style(dark=False) == "default"


def test_preview_renders_the_style_selected_in_its_own_combo(qapp):
    dialog = PreferencesDialog()
    dialog._dark_combo.setCurrentText("monokai")
    assert _keyword_color(dialog._dark_preview) == _style_keyword_color("monokai")
    # The light preview keeps showing its own selection, not the dark one.
    assert _keyword_color(dialog._light_preview) == _style_keyword_color("default")


def test_preview_paints_the_background_of_the_style(qapp):
    # Unlike the editing fields, the preview must show the style's own
    # background -- a dark style previewed on a light dialog would otherwise
    # render dark text on a light field, which is not what the user gets.
    dialog = PreferencesDialog()
    dialog._dark_combo.setCurrentText("monokai")
    base = dialog._dark_preview.palette().color(QPalette.ColorRole.Base)
    assert base.name() == get_style_by_name("monokai").background_color


def test_preview_text_stays_readable_when_the_style_declares_no_base_color(qapp):
    # `dracula` has a dark background but leaves the root token undecorated;
    # taken literally, undecorated text would come out black on near-black.
    dialog = PreferencesDialog()
    dialog._dark_combo.setCurrentText("dracula")
    preview = dialog._dark_preview
    assert preview.palette().color(QPalette.ColorRole.Text).lightness() > 128


def test_preview_is_read_only(qapp):
    dialog = PreferencesDialog()
    assert dialog._light_preview.isReadOnly()
    assert dialog._dark_preview.isReadOnly()


def test_dialog_preselects_the_saved_indent_width(qapp):
    save_indent_width(2)
    dialog = PreferencesDialog()
    assert dialog._indent_spin.value() == 2


def test_changing_the_indent_width_saves_it(qapp):
    dialog = PreferencesDialog()
    dialog._indent_spin.setValue(8)
    assert load_indent_width() == 8


def test_the_indent_spinbox_cannot_leave_the_supported_range(qapp):
    dialog = PreferencesDialog()
    assert dialog._indent_spin.minimum() == MIN_INDENT_WIDTH
    assert dialog._indent_spin.maximum() == MAX_INDENT_WIDTH
