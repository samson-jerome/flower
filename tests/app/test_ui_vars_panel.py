from flower.engine.models.node import Variable, VariableOperation
from flower.app.vars_panel import VarsPanel


def test_vars_panel_set_get_roundtrip(qapp):
    panel = VarsPanel()
    variables = [
        Variable(name="FOO", value="bar", active=True, operation=VariableOperation.ASSIGN),
        Variable(name="BAZ", value="42", active=False, operation=VariableOperation.CONCAT),
    ]
    panel.set_variables(variables)
    result = panel.get_variables()
    assert len(result) == 2
    assert result[0].name == "FOO"
    assert result[1].active is False
    assert result[1].operation == VariableOperation.CONCAT


def test_vars_panel_unknown_operation_falls_back_to_assign(qapp):
    panel = VarsPanel()
    panel.set_variables([Variable(name="ENV", value="prod", operation="+=")])
    result = panel.get_variables()
    assert result[0].operation == VariableOperation.ASSIGN


def test_vars_panel_add_row(qapp):
    panel = VarsPanel()
    panel._add_row()
    assert panel._table.rowCount() == 1


def test_vars_panel_add_row_defaults_to_assign_operation(qapp):
    panel = VarsPanel()
    panel._add_row()
    assert panel.get_variables()[0].operation == VariableOperation.ASSIGN


def test_vars_panel_emits_variables_changed_on_add_row(qapp):
    panel = VarsPanel()
    received = []
    panel.variables_changed.connect(lambda: received.append(True))
    panel._add_row()
    assert received == [True]


def test_vars_panel_emits_variables_changed_on_delete_row(qapp):
    panel = VarsPanel()
    panel._add_row()
    panel._table.selectRow(0)
    received = []
    panel.variables_changed.connect(lambda: received.append(True))
    panel._delete_selected()
    assert received == [True]


def test_vars_panel_emits_variables_changed_on_cell_edit(qapp):
    panel = VarsPanel()
    panel._add_row()
    received = []
    panel.variables_changed.connect(lambda: received.append(True))
    panel._table.item(0, 0).setText("NEW_NAME")
    assert received == [True]


def test_vars_panel_emits_variables_changed_on_checkbox_toggle(qapp):
    panel = VarsPanel()
    panel._add_row()
    received = []
    panel.variables_changed.connect(lambda: received.append(True))
    panel._table.cellWidget(0, 3).setChecked(False)
    assert received == [True]


def test_vars_panel_emits_variables_changed_on_operation_change(qapp):
    panel = VarsPanel()
    panel._add_row()
    received = []
    panel.variables_changed.connect(lambda: received.append(True))
    panel._table.cellWidget(0, 4).setCurrentIndex(1)
    assert received == [True]


def test_vars_panel_set_variables_does_not_emit_variables_changed(qapp):
    panel = VarsPanel()
    received = []
    panel.variables_changed.connect(lambda: received.append(True))
    panel.set_variables([Variable(name="ENV", value="prod")])
    assert received == []
