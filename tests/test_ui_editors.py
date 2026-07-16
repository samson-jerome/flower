from flower.models.node import NodeType
from flower.ui.editor.type_editors import make_type_editor, ScriptEditor, LoopEditor


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
