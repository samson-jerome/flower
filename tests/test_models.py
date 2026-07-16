from flower.models.node import Variable, VariableOperation, NodeType, Node
from flower.models.graph import Graph


def test_variable_defaults():
    v = Variable(name="FOO", value="bar")
    assert v.description == ""
    assert v.active is True
    assert v.operation == VariableOperation.ASSIGN


def test_variable_operation_enum_values():
    assert VariableOperation.ASSIGN == "assign"
    assert VariableOperation.CONCAT == "concat"
    assert VariableOperation.ADD == "add"


def test_node_type_values():
    assert NodeType.SCRIPT == "script"
    assert NodeType.LOOP == "loop"
    assert NodeType.IF == "if"
    assert NodeType.DATA == "data"
    assert NodeType.NOOP == "noop"


def test_node_defaults():
    node = Node(id="n1", name="build", type=NodeType.SCRIPT)
    assert node.is_active is True
    assert node.is_collapsed is False
    assert node.description == ""
    assert node.variables == []
    assert node.type_data == {}
    assert node.children == []
    assert node.parent is None


def test_node_parent_excluded_from_repr():
    parent = Node(id="p", name="parent", type=NodeType.NOOP)
    child = Node(id="c", name="child", type=NodeType.NOOP, parent=parent)
    assert "parent" not in repr(child)


def test_graph_defaults():
    g = Graph()
    assert g.roots == []
    assert g.variables == []
    assert g.created_at == ""
    assert g.updated_at == ""


def test_max_children_limits_if_nodes_to_two():
    from flower.models.node import MAX_CHILDREN
    assert MAX_CHILDREN[NodeType.IF] == 2


def test_max_children_has_no_limit_for_other_types():
    from flower.models.node import MAX_CHILDREN
    assert MAX_CHILDREN.get(NodeType.NOOP) is None
    assert MAX_CHILDREN.get(NodeType.SCRIPT) is None
    assert MAX_CHILDREN.get(NodeType.DATA) is None
    assert MAX_CHILDREN.get(NodeType.LOOP) is None
