from flower.models.node import Variable
from flower.ui.vars_panel import VarsPanel


def test_vars_panel_set_get_roundtrip(qapp):
    panel = VarsPanel()
    variables = [
        Variable(name="FOO", value="bar", active=True, operation="="),
        Variable(name="BAZ", value="42", active=False, operation="+="),
    ]
    panel.set_variables(variables)
    result = panel.get_variables()
    assert len(result) == 2
    assert result[0].name == "FOO"
    assert result[1].active is False
    assert result[1].operation == "+="


def test_vars_panel_add_row(qapp):
    panel = VarsPanel()
    panel._add_row()
    assert panel._table.rowCount() == 1
