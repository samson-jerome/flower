import uuid
from flower.models.node import Node, NodeType, Variable
from flower.ui.editor.node_form import NodeForm


def _make_node():
    return Node(
        id=str(uuid.uuid4()), name="build", type=NodeType.SCRIPT,
        type_data={"language": "bash", "body": "make build"},
        variables=[Variable(name="X", value="1")],
    )


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
    form._name.setText("deploy")
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
