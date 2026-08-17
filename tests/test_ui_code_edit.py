import pytest
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from flower.ui import indent as indent_mod
from flower.ui.editor.code_edit import CodeEdit


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        indent_mod, "QSettings",
        lambda: QSettings(ini_path, QSettings.Format.IniFormat),
    )


def test_tab_inserts_four_spaces_by_default(qapp):
    edit = CodeEdit()
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    assert edit.toPlainText() == "    "


def test_tab_never_inserts_a_tab_character(qapp):
    edit = CodeEdit()
    edit.setPlainText("echo ok")
    edit.moveCursor(edit.textCursor().MoveOperation.Start)
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    assert "\t" not in edit.toPlainText()
    assert edit.toPlainText() == "    echo ok"


def test_tab_honours_the_configured_width(qapp):
    indent_mod.save_indent_width(2)
    edit = CodeEdit()
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    assert edit.toPlainText() == "  "


def test_the_width_is_re_read_between_keystrokes(qapp):
    """The field is built once per NodeForm and outlives the preferences
    dialog, so a width changed while it is open has to take effect."""
    edit = CodeEdit()
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    indent_mod.save_indent_width(8)
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    assert edit.toPlainText() == " " * 4 + " " * 8


def test_tab_inserts_at_the_cursor_not_at_the_line_start(qapp):
    edit = CodeEdit()
    edit.setPlainText("if x:")
    edit.moveCursor(edit.textCursor().MoveOperation.End)
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    assert edit.toPlainText() == "if x:    "


def test_other_keys_are_left_to_qt(qapp):
    edit = CodeEdit()
    QTest.keyClicks(edit, "abc")
    assert edit.toPlainText() == "abc"


def test_the_font_is_monospace(qapp):
    assert CodeEdit().font().styleHint() == QFont.StyleHint.Monospace


def test_a_read_only_field_inserts_nothing(qapp):
    # setReadOnly blocks Qt's own key handling, not a programmatic
    # insertText -- the Tab branch has to check for itself.
    edit = CodeEdit()
    edit.setReadOnly(True)
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    assert edit.toPlainText() == ""
