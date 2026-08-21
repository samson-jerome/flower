import pytest
from PySide6.QtCore import Qt, QSettings
from PySide6.QtTest import QTest
from pygments.styles import get_style_by_name
from pygments.token import Token
from flower.app import indent as indent_mod
from flower.engine.models.node import NodeType
from flower.app import highlight_styles
from flower.app.editor import highlighter as highlighter_mod
from flower.app.editor.type_editors import (
    make_type_editor, DataEditor, ScriptEditor, LoopEditor,
)


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
    assert editor._mode_expression.isChecked()
    assert editor._stack.currentWidget() is editor._expression


def test_loop_editor_switching_mode_keeps_other_modes_values(qapp):
    # get_data() always returns every key, so toggling modes loses nothing.
    editor = LoopEditor()
    editor.set_data({
        "index": "f", "mode": "expression", "start": 2, "end": 8, "step": 3,
        "items": "a\nb", "expression": "ls",
    })
    editor._mode_range.setChecked(True)
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
    assert editor._mode_range.isChecked()
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
    assert not editor._language.isEditable()


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
    editor._language.setCurrentText("bash")
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
    assert editor._highlighter.document() is editor._expression.document()


def test_data_editor_highlights_the_content_as_python(qapp):
    # Fixed lexer: the DATA node declares no language, and python is the
    # closest fit for the structured payloads it usually carries.
    editor = DataEditor()
    editor.set_data({"command": "cat", "content": 'x = {"a": 1}  # note'})
    assert editor._highlighter.document() is editor._content.document()
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
    (ScriptEditor, "_body",       {"language": "bash", "body": ""}),
    (DataEditor,   "_content",    {"command": "", "content": ""}),
    (LoopEditor,   "_expression", {"index": "f", "mode": "expression", "start": 0,
                                   "end": 0, "step": 1, "items": "", "expression": ""}),
])
def test_tab_indents_with_spaces_in_every_code_field(
    qapp, isolated_indent_settings, editor_class, field, data
):
    editor = editor_class()
    editor.set_data(data)
    widget = getattr(editor, field)
    QTest.keyClick(widget, Qt.Key.Key_Tab)
    assert widget.toPlainText() == "    "


def test_the_loop_items_field_keeps_the_plain_tab_behaviour(qapp):
    # Liste mode holds literal values, not code -- it is not a CodeEdit, the
    # same reason it carries no highlighter.
    editor = LoopEditor()
    assert type(editor._items) is not type(editor._expression)
