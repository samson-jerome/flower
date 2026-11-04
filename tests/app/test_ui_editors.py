import pytest
from PySide6.QtCore import Qt, QSettings
from PySide6.QtTest import QTest
from pygments.styles import get_style_by_name
from pygments.token import Token
from flower.app.prefs import indent as indent_mod
from flower.engine.models.node import NodeType
from flower.app.prefs import highlight_styles
from flower.app.editor import highlighter as highlighter_mod
from operator import attrgetter
from flower.app.editor.type_editors import (
    make_type_editor, DataEditor, ScriptEditor, LoopEditor, IfEditor, LOOP_MODES,
)
from flower.app.editor.code_edit import CodeEdit


def test_script_editor_roundtrip(qapp):
    editor = ScriptEditor()
    data = {"language": "python", "body": "print('hello')"}
    editor.set_data(data)
    result = editor.get_data()
    assert result["language"] == "python"
    assert result["body"] == "print('hello')"


def test_loop_editor_range_roundtrip(qapp):
    editor = LoopEditor()
    editor.set_data({"index": "i", "mode": "range", "start": 1, "end": 10, "step": 2, "items": ""})
    result = editor.get_data()
    assert result["mode"] == "range"
    assert result["start"] == 1
    assert result["end"] == 10


def test_loop_editor_list_roundtrip(qapp):
    editor = LoopEditor()
    editor.set_data({"index": "item", "mode": "list", "start": 0, "end": 0, "step": 1, "items": "a\nb\nc"})
    result = editor.get_data()
    assert result["mode"] == "list"
    assert result["items"] == "a\nb\nc"


def test_loop_editor_expression_roundtrip(qapp):
    editor = LoopEditor()
    editor.set_data({
        "index": "f", "mode": "expression", "start": 0, "end": 0, "step": 1,
        "items": "", "expression": "ls ~/*.*",
    })
    result = editor.get_data()
    assert result["mode"] == "expression"
    assert result["expression"] == "ls ~/*.*"
    assert result["index"] == "f"


def test_loop_editor_expression_selects_its_stack_page(qapp):
    editor = LoopEditor()
    editor.set_data({"index": "f", "mode": "expression", "expression": "ls"})
    assert editor._mode.value() == "expression"
    assert editor._stack.currentWidget() is editor._expression.parentWidget()


def test_loop_editor_switching_mode_keeps_other_modes_values(qapp):
    # get_data() always returns every key, so toggling modes loses nothing.
    editor = LoopEditor()
    editor.set_data({
        "index": "f", "mode": "expression", "start": 2, "end": 8, "step": 3,
        "items": "a\nb", "expression": "ls",
    })
    editor._mode.combo.setCurrentIndex(LOOP_MODES.index("range"))
    result = editor.get_data()
    assert result["mode"] == "range"
    assert result["start"] == 2
    assert result["end"] == 8
    assert result["step"] == 3
    assert result["items"] == "a\nb"
    assert result["expression"] == "ls"


def test_loop_editor_unknown_mode_falls_back_to_range(qapp):
    editor = LoopEditor()
    editor.set_data({"index": "i", "mode": "legacy", "start": 0, "end": 1, "step": 1})
    assert editor._mode.value() == "range"
    assert editor.get_data()["mode"] == "range"


def test_loop_editor_missing_expression_key_yields_empty_string(qapp):
    editor = LoopEditor()
    editor.set_data({"index": "i", "mode": "range", "start": 0, "end": 1, "step": 1})
    assert editor.get_data()["expression"] == ""


def test_make_type_editor_all_types(qapp):
    for ntype in NodeType:
        w = make_type_editor(ntype)
        assert w is not None


def test_script_editor_language_combo_is_not_editable(qapp):
    editor = ScriptEditor()
    assert not editor._language.combo.isEditable()


def test_script_editor_unknown_language_falls_back_to_bash(qapp):
    editor = ScriptEditor()
    editor.set_data({"language": "ruby", "body": "puts 1"})
    assert editor.get_data()["language"] == "bash"


def test_script_editor_highlights_its_body(qapp):
    editor = ScriptEditor()
    editor.set_data({"language": "python", "body": "import os\n"})
    assert editor._highlighter._spans()


def test_script_editor_combo_drives_the_highlighter(qapp):
    editor = ScriptEditor()
    editor.set_data({"language": "python", "body": "import os\n"})
    python_spans = len(editor._highlighter._spans())
    editor._language.combo.setCurrentText("bash")
    assert len(editor._highlighter._spans()) != python_spans


def test_script_editor_set_data_applies_the_language(qapp):
    # set_data may leave the combo index unchanged, so it must set the
    # language explicitly rather than rely on the signal.
    editor = ScriptEditor()
    editor.set_data({"language": "bash", "body": "echo ok\n"})
    bash_spans = editor._highlighter._spans()
    editor.set_data({"language": "python", "body": "echo ok\n"})
    assert editor._highlighter._spans() != bash_spans


def test_script_editor_unknown_language_highlights_as_bash(qapp):
    editor = ScriptEditor()
    editor.set_data({"language": "ruby", "body": "echo ok\n"})
    assert editor._highlighter._spans()


def test_loop_editor_highlights_the_expression_as_bash(qapp):
    editor = LoopEditor()
    editor.set_data({
        "index": "f", "mode": "expression", "start": 0, "end": 0, "step": 1,
        "items": "", "expression": "ls ~/*.* | sort",
    })
    assert editor._highlighter._spans()


def test_loop_editor_items_field_is_not_highlighted(qapp):
    # The Liste mode holds literal values, one per line -- not code.
    editor = LoopEditor()
    assert editor._highlighter.document() is editor._expression.edit.document()


def test_data_editor_highlights_the_content_as_python(qapp):
    # Fixed lexer: the DATA node declares no language, and python is the
    # closest fit for the structured payloads it usually carries.
    editor = DataEditor()
    editor.set_data({"command": "cat", "content": 'x = {"a": 1}  # note'})
    assert editor._highlighter.document() is editor._content.edit.document()
    assert editor._highlighter._spans()


def test_data_editor_command_field_is_not_highlighted(qapp):
    # `Commande:` is a single-line QLineEdit -- a highlighter needs a document.
    editor = DataEditor()
    assert editor._highlighter.document() is not editor._command


@pytest.mark.parametrize("editor_class", [ScriptEditor, LoopEditor, DataEditor])
def test_a_style_preference_change_reaches_an_open_editor(qapp, monkeypatch, editor_class):
    """Node editors are non-modal, so one can sit open behind the preferences
    dialog. It must repaint on the new style, not on the next reopening."""
    editor = editor_class()
    monkeypatch.setattr(highlighter_mod, "load_style", lambda dark: "monokai")
    highlight_styles.notifier.changed.emit()
    expected = "#" + get_style_by_name("monokai").style_for_token(Token.Keyword)["color"]
    assert editor._highlighter._format_for(Token.Keyword).foreground().color().name() == expected


@pytest.fixture
def isolated_indent_settings(tmp_path, monkeypatch):
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        indent_mod, "QSettings",
        lambda: QSettings(ini_path, QSettings.Format.IniFormat),
    )


@pytest.mark.parametrize("editor_class, field, data", [
    (ScriptEditor, "_body.edit",    {"language": "bash", "body": ""}),
    (DataEditor,   "_content.edit", {"command": "", "content": ""}),
    (LoopEditor,   "_expression.edit", {"index": "f", "mode": "expression", "start": 0,
                                   "end": 0, "step": 1, "items": "", "expression": ""}),
])
def test_tab_indents_with_spaces_in_every_code_field(
    qapp, isolated_indent_settings, editor_class, field, data
):
    editor = editor_class()
    editor.set_data(data)
    widget = attrgetter(field)(editor)
    QTest.keyClick(widget, Qt.Key.Key_Tab)
    assert widget.toPlainText() == "    "


def test_the_loop_items_field_keeps_the_plain_tab_behaviour(qapp):
    # Liste mode holds literal values, not code -- it is not a CodeEdit, the
    # same reason it carries no highlighter.
    editor = LoopEditor()
    assert type(editor._items.text) is not type(editor._expression.edit)


def test_script_editor_body_fills_the_editor(qapp):
    editor = ScriptEditor()
    editor.resize(400, 800)
    editor.show()
    qapp.processEvents()
    assert editor._body.edit.height() > 600


def test_if_editor_roundtrip(qapp):
    editor = IfEditor()
    editor.set_data({"condition": "[ -n x ]"})
    assert editor.get_data() == {"condition": "[ -n x ]"}


def test_data_editor_takes_typed_values_without_focus_out(qapp):
    editor = DataEditor()
    editor.set_data({"command": "", "content": ""})
    editor._command.text.setText("cat")
    editor._content.edit.setPlainText("x")
    assert editor.get_data() == {"command": "cat", "content": "x"}


def test_script_editor_unknown_language_shows_bash(qapp):
    editor = ScriptEditor()
    editor.set_data({"language": "ruby", "body": ""})
    assert editor._language.combo.currentText() == "bash"


def test_loop_mode_combo_selects_the_matching_page(qapp):
    editor = LoopEditor()
    for i, mode in enumerate(LOOP_MODES):
        editor._mode.combo.setCurrentIndex(i)
        assert editor._stack.currentIndex() == i
        assert editor.get_data()["mode"] == mode


def test_loop_numbers_given_as_strings_come_back_as_ints(qapp):
    editor = LoopEditor()
    editor.set_data({"index": "i", "mode": "range", "start": "3", "end": "7", "step": "2"})
    data = editor.get_data()
    assert (data["start"], data["end"], data["step"]) == (3, 7, 2)


def test_loop_numbers_are_clamped_to_the_current_bounds(qapp):
    editor = LoopEditor()
    editor.set_data({"index": "i", "mode": "range", "start": -20000, "end": 20000, "step": 0})
    data = editor.get_data()
    assert (data["start"], data["end"], data["step"]) == (-9999, 9999, 1)


def test_loop_typed_number_is_taken_without_focus_out(qapp):
    editor = LoopEditor()
    editor.set_data({"index": "i", "mode": "range"})
    # Real keystrokes: the line edit commits on textEdited, which setText()
    # does not emit.
    editor._end.line.selectAll()
    QTest.keyClicks(editor._end.line, "42")
    assert editor.get_data()["end"] == 42


def test_loop_items_is_not_a_code_edit(qapp):
    editor = LoopEditor()
    assert not isinstance(editor._items.text, CodeEdit)


def test_loop_items_field_sits_at_the_top_of_its_page(qapp):
    # The items area sizes itself to its lines; stretching its row would
    # centre it in the leftover height instead.
    editor = LoopEditor()
    editor.set_data({"index": "i", "mode": "list", "items": "a\nb"})
    editor.resize(400, 600)
    editor.show()
    qapp.processEvents()
    page = editor._stack.currentWidget()
    assert editor._items.text.mapTo(page, editor._items.text.rect().topLeft()).y() < 20


def _clear_and_type(line, text):
    line.selectAll()
    QTest.keyClick(line, Qt.Key.Key_Backspace)
    if text:
        QTest.keyClicks(line, text)


@pytest.mark.parametrize("typed", ["", "0"])
def test_loop_step_keeps_its_last_valid_value_on_incomplete_input(qapp, typed):
    # A step of 0 would generate a bash loop that never ends.
    editor = LoopEditor()
    editor.set_data({"index": "i", "mode": "range", "step": 3})
    _clear_and_type(editor._step.line, typed)
    assert editor.get_data()["step"] == 3


def test_loop_cleared_start_keeps_its_last_valid_value(qapp):
    editor = LoopEditor()
    editor.set_data({"index": "i", "mode": "range", "start": 5})
    _clear_and_type(editor._start.line, "")
    assert editor.get_data()["start"] == 5


def test_loop_incomplete_number_is_restored_on_focus_out(qapp):
    # What the field shows once left is what get_data() returns.
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QFocusEvent
    editor = LoopEditor()
    editor.set_data({"index": "i", "mode": "range", "step": 3})
    _clear_and_type(editor._step.line, "0")
    qapp.sendEvent(editor._step.line, QFocusEvent(QEvent.Type.FocusOut))
    assert editor._step.line.text() == "3"


def test_loop_items_field_grows_while_typing(qapp):
    editor = LoopEditor()
    editor.set_data({"index": "i", "mode": "list", "items": ""})
    before = editor._items.text.height()
    editor._items.text.setPlainText("\n".join("abcdefghijk"))
    assert editor._items.text.height() > before
