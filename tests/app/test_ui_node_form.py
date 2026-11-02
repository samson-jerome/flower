import uuid
from PySide6.QtWidgets import QMessageBox
from flower.engine.models.node import Node, NodeType, Variable
from qt_parameters import ParameterForm
from flower.app.editor.node_form import NodeForm


def _make_node():
    return Node(
        id=str(uuid.uuid4()), name="build", type=NodeType.SCRIPT,
        type_data={"language": "bash", "body": "make build"},
        variables=[Variable(name="X", value="1")],
    )


def _make_node_with_children(count):
    node = Node(id=str(uuid.uuid4()), name="check", type=NodeType.NOOP)
    for i in range(count):
        child = Node(id=str(uuid.uuid4()), name=f"child{i}", type=NodeType.NOOP)
        child.parent = node
        node.children.append(child)
    return node


def test_node_form_initial_values(qapp):
    node = _make_node()
    form = NodeForm(node)
    data = form.get_node_data()
    assert data["name"] == "build"
    assert data["type"] == NodeType.SCRIPT
    assert data["is_active"] is True


def test_node_form_apply_to_node(qapp):
    node = _make_node()
    form = NodeForm(node)
    form._name.text.setText("deploy")
    updated = form.apply_to_node()
    assert updated.name == "deploy"
    assert updated is node


def test_description_section_edits_node_description(qapp):
    node = _make_node()
    node.description = "initial"
    form = NodeForm(node)
    assert form._description.text() == "initial"
    form._description.set_text("updated")
    assert form.apply_to_node().description == "updated"


def test_variables_checkbox_collapses_section(qapp):
    node = _make_node()
    form = NodeForm(node)
    form.show()
    assert form._vars._content.isVisible()
    form._vars._toggle.click()
    assert not form._vars._content.isVisible()
    assert form._vars._toggle.isVisible()  # header stays
    form._vars._toggle.click()
    assert form._vars._content.isVisible()


def test_variables_survive_collapse(qapp):
    node = _make_node()
    form = NodeForm(node)
    form._vars.set_collapsed(True)
    data = form.get_node_data()
    assert [v.name for v in data["variables"]] == ["X"]


def test_type_change_to_if_blocked_when_too_many_children(qapp, monkeypatch):
    node = _make_node_with_children(3)
    form = NodeForm(node)
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warned.append(a)))

    form._type_combo.combo.setCurrentText("if")

    assert warned
    assert form._type_combo.value() == NodeType.NOOP
    assert node.type == NodeType.NOOP


def test_type_change_to_if_allowed_with_two_children(qapp, monkeypatch):
    node = _make_node_with_children(2)
    form = NodeForm(node)
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warned.append(a)))

    form._type_combo.combo.setCurrentText("if")

    assert not warned
    assert form._type_combo.value() == NodeType.IF


def test_type_change_to_if_allowed_with_no_children(qapp, monkeypatch):
    node = _make_node_with_children(0)
    form = NodeForm(node)
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warned.append(a)))

    form._type_combo.combo.setCurrentText("if")

    assert not warned
    assert form._type_combo.value() == NodeType.IF


def _data_node():
    return Node(
        id=str(uuid.uuid4()), name="payload", type=NodeType.DATA,
        type_data={"command": "cat", "content": "x"},
    )


def test_executable_row_is_enabled_for_a_script_node(qapp):
    form = NodeForm(_make_node())
    assert form._executable.isEnabled() is True
    assert form._executable.value() is False


def test_executable_row_is_enabled_for_a_data_node(qapp):
    form = NodeForm(_data_node())
    assert form._executable.isEnabled() is True


def test_executable_row_is_disabled_for_a_noop_node(qapp):
    node = Node(id=str(uuid.uuid4()), name="step", type=NodeType.NOOP)
    form = NodeForm(node)
    assert form._executable.isEnabled() is False


def test_executable_row_reflects_the_node_flag(qapp):
    node = _make_node()
    node.is_executable = True
    assert NodeForm(node)._executable.value() is True


def test_get_node_data_carries_the_executable_flag(qapp):
    form = NodeForm(_make_node())
    form._executable.set_value(True)
    assert form.get_node_data()["is_executable"] is True


def test_apply_to_node_writes_the_executable_flag(qapp):
    node = _make_node()
    form = NodeForm(node)
    form._executable.set_value(True)
    assert form.apply_to_node().is_executable is True


def test_switching_to_an_ineligible_type_disables_the_executable_row(qapp):
    node = _make_node()
    node.is_executable = True
    form = NodeForm(node)
    form._type_combo.combo.setCurrentText(NodeType.IF.value)
    assert form._executable.isEnabled() is False
    assert form.get_node_data()["is_executable"] is False


def test_a_round_trip_through_an_ineligible_type_keeps_the_checked_flag(qapp):
    node = _make_node()
    form = NodeForm(node)
    form._executable.set_value(True)

    form._type_combo.combo.setCurrentText(NodeType.NOOP.value)
    form._type_combo.combo.setCurrentText(NodeType.SCRIPT.value)

    assert form._executable.value() is True
    assert form._executable.isEnabled() is True
    assert form.get_node_data()["is_executable"] is True


def test_exec_state_changed_follows_the_executable_checkbox(qapp):
    form = NodeForm(_make_node())
    received = []
    form.exec_state_changed.connect(received.append)
    form._executable.set_value(True)
    assert received == [True]
    form._executable.set_value(False)
    assert received == [True, False]


def test_exec_state_changed_follows_the_active_checkbox(qapp):
    form = NodeForm(_make_node())
    form._executable.set_value(True)
    received = []
    form.exec_state_changed.connect(received.append)
    form._active.set_value(False)
    assert received == [False]


def test_exec_state_changed_follows_the_type_combo(qapp):
    form = NodeForm(_make_node())
    form._executable.set_value(True)
    received = []
    form.exec_state_changed.connect(received.append)
    form._type_combo.combo.setCurrentText(NodeType.LOOP.value)
    assert received[-1] is False


def test_executable_row_resyncs_after_a_refused_type_change(qapp, monkeypatch):
    node = Node(
        id=str(uuid.uuid4()), name="build", type=NodeType.SCRIPT,
        type_data={"language": "bash", "body": "make build"},
    )
    for i in range(3):
        child = Node(id=str(uuid.uuid4()), name=f"child{i}", type=NodeType.NOOP)
        child.parent = node
        node.children.append(child)
    form = NodeForm(node)
    form._executable.set_value(True)
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    # Step 1: switch to an eligible-for-nothing type -- allowed, disables the row.
    form._type_combo.combo.setCurrentText(NodeType.NOOP.value)
    assert form._executable.isEnabled() is False

    # Step 2: switch to "if" -- refused because of the 3 children, combo reverts
    # to "script". The row must follow the reverted type, not stay stale. The
    # checkbox itself was never cleared by the ineligible NOOP step, so once
    # back on "script" (active, executable) the exec state is live again.
    received = []
    form.exec_state_changed.connect(received.append)
    form._type_combo.combo.setCurrentText(NodeType.IF.value)

    assert form._type_combo.value() == NodeType.SCRIPT
    assert form._executable.isEnabled() is True
    assert received[-1] is True


def test_refused_type_change_restores_the_visible_editor(qapp, monkeypatch):
    node = Node(
        id=str(uuid.uuid4()), name="build", type=NodeType.SCRIPT,
        type_data={"language": "bash", "body": "make build"},
    )
    for i in range(3):
        child = Node(id=str(uuid.uuid4()), name=f"child{i}", type=NodeType.NOOP)
        child.parent = node
        node.children.append(child)
    form = NodeForm(node)
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    # Refused because of the 3 children -- the combo reverts to "script", and
    # the stack must show the script editor again, not the refused "if" one.
    form._type_combo.combo.setCurrentText(NodeType.IF.value)

    assert form._stack.currentWidget() is form._type_editors[NodeType.SCRIPT]


def test_refused_type_change_keeps_unapplied_edits(qapp, monkeypatch):
    node = _make_node()
    for i in range(3):
        child = Node(id=str(uuid.uuid4()), name=f"c{i}", type=NodeType.NOOP)
        child.parent = node
        node.children.append(child)
    form = NodeForm(node)
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    form._type_editors[NodeType.SCRIPT]._body.edit.setPlainText("edited")

    form._type_combo.combo.setCurrentText(NodeType.IF.value)

    assert form._type_combo.value() == NodeType.SCRIPT
    assert form.get_node_data()["type_data"]["body"] == "edited"


def test_executable_label_follows_the_row_state(qapp):
    form = NodeForm(Node(id=str(uuid.uuid4()), name="s", type=NodeType.NOOP))
    assert ParameterForm.label(form._executable).isEnabled() is False


def test_code_field_takes_most_of_the_body(qapp):
    form = NodeForm(_make_node())
    form.resize(480, 1200)
    form.show()
    qapp.processEvents()
    code = form._type_editors[NodeType.SCRIPT]._body.edit
    assert code.height() >= form._body.scroll_area.viewport().height() // 2
