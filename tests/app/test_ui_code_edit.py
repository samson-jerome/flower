import pytest
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtTest import QTest
from flower.app import indent as indent_mod
from flower.app.editor.code_edit import CodeEdit


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


def _select(edit, start, end):
    cursor = edit.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    edit.setTextCursor(cursor)


def _put_cursor(edit, position):
    cursor = edit.textCursor()
    cursor.setPosition(position)
    edit.setTextCursor(cursor)


def _shift_tab(edit):
    QTest.keyClick(edit, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)


def test_tab_indents_every_selected_line(qapp):
    edit = CodeEdit()
    edit.setPlainText("un\ndeux\ntrois")
    _select(edit, 0, len("un\ndeux\ntrois"))
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    assert edit.toPlainText() == "    un\n    deux\n    trois"


def test_tab_on_a_single_line_selection_still_replaces_it(qapp):
    # Only a multi-line selection switches to block indenting.
    edit = CodeEdit()
    edit.setPlainText("un\ndeux")
    _select(edit, 0, 2)
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    assert edit.toPlainText() == "    \ndeux"


def test_tab_ignores_a_last_line_the_selection_only_touches(qapp):
    # The selection ends at column 0 of "trois", so that line is not indented.
    edit = CodeEdit()
    edit.setPlainText("un\ndeux\ntrois")
    _select(edit, 0, len("un\ndeux\n"))
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    assert edit.toPlainText() == "    un\n    deux\ntrois"


def test_the_selection_survives_indenting(qapp):
    edit = CodeEdit()
    edit.setPlainText("un\ndeux")
    _select(edit, 0, len("un\ndeux"))
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    assert edit.toPlainText() == "        un\n        deux"


def test_the_restored_selection_covers_whole_lines(qapp):
    edit = CodeEdit()
    edit.setPlainText("un\ndeux")
    _select(edit, 1, 4)  # from mid-"un" to mid-"deux"
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    cursor = edit.textCursor()
    assert cursor.selectionStart() == 0
    assert cursor.selectionEnd() == len("    un\n    deux")


def test_indenting_a_block_undoes_in_one_step(qapp):
    edit = CodeEdit()
    edit.setPlainText("un\ndeux\ntrois")
    _select(edit, 0, len("un\ndeux\ntrois"))
    QTest.keyClick(edit, Qt.Key.Key_Tab)
    edit.undo()
    assert edit.toPlainText() == "un\ndeux\ntrois"


def test_shift_tab_dedents_the_cursor_line(qapp):
    edit = CodeEdit()
    edit.setPlainText("    echo ok")
    _put_cursor(edit, len("    echo"))
    _shift_tab(edit)
    assert edit.toPlainText() == "echo ok"


def test_shift_tab_dedents_every_selected_line(qapp):
    edit = CodeEdit()
    edit.setPlainText("    un\n    deux")
    _select(edit, 0, len("    un\n    deux"))
    _shift_tab(edit)
    assert edit.toPlainText() == "un\ndeux"


def test_shift_tab_removes_only_the_spaces_that_are_there(qapp):
    edit = CodeEdit()
    edit.setPlainText("  deux seulement")
    _put_cursor(edit, 0)
    _shift_tab(edit)
    assert edit.toPlainText() == "deux seulement"


def test_shift_tab_removes_a_leading_tab_character(qapp):
    # A .flow written before Tab inserted spaces holds real tab characters.
    edit = CodeEdit()
    edit.setPlainText("\techo ok")
    _put_cursor(edit, 0)
    _shift_tab(edit)
    assert edit.toPlainText() == "echo ok"


def test_shift_tab_leaves_an_unindented_line_alone(qapp):
    edit = CodeEdit()
    edit.setPlainText("echo ok")
    _put_cursor(edit, 0)
    _shift_tab(edit)
    assert edit.toPlainText() == "echo ok"


def test_shift_tab_dedents_by_the_configured_width(qapp):
    indent_mod.save_indent_width(2)
    edit = CodeEdit()
    edit.setPlainText("    echo ok")
    _put_cursor(edit, 0)
    _shift_tab(edit)
    assert edit.toPlainText() == "  echo ok"


def test_a_read_only_field_ignores_shift_tab(qapp):
    edit = CodeEdit()
    edit.setPlainText("    echo ok")
    edit.setReadOnly(True)
    _put_cursor(edit, 0)
    _shift_tab(edit)
    assert edit.toPlainText() == "    echo ok"
