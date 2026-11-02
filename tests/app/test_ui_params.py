from qt_parameters import ParameterForm
from flower.app.editor.code_edit import CodeEdit
from flower.app.editor.params import (
    LiveStringParameter, CodeParameter, setup_form, stretch_last_row,
)


def test_live_string_parameter_follows_typing_without_focus_out(qapp):
    p = LiveStringParameter("name")
    p.text.setText("typed")
    assert p.value() == "typed"


def test_live_string_parameter_area_follows_typing(qapp):
    p = LiveStringParameter("items")
    p.set_area(True)
    p.text.setPlainText("a\nb")
    assert p.value() == "a\nb"


def test_live_string_parameter_set_value_updates_the_widget(qapp):
    p = LiveStringParameter("name")
    p.set_value("x")
    assert p.text.text() == "x"


def test_code_parameter_wraps_a_code_edit(qapp):
    assert isinstance(CodeParameter("body").edit, CodeEdit)


def test_code_parameter_value_follows_typing(qapp):
    p = CodeParameter("body")
    seen = []
    p.value_changed.connect(seen.append)
    p.edit.setPlainText("echo 1")
    assert p.value() == "echo 1"
    assert seen == ["echo 1"]


def test_code_parameter_set_value_does_not_echo(qapp):
    p = CodeParameter("body")
    seen = []
    p.value_changed.connect(seen.append)
    p.set_value("ls")
    assert p.edit.toPlainText() == "ls"
    assert seen == ["ls"]


def test_stretch_last_row_lets_a_code_field_fill_the_form(qapp):
    form = setup_form(ParameterForm(), nested=False)
    form.add_parameter(LiveStringParameter("cmd"))
    code = form.add_parameter(CodeParameter("body"))
    stretch_last_row(form)
    form.resize(400, 800)
    form.show()
    qapp.processEvents()
    assert code.edit.height() > 600
