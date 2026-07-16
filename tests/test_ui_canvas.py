import uuid
from flower.models.node import Node, NodeType
from flower.models.graph import Graph
from flower.ui.canvas import GraphCanvas


def _node(name, ntype=NodeType.NOOP):
    return Node(id=str(uuid.uuid4()), name=name, type=ntype)


def test_canvas_load_graph(qapp):
    root  = _node("root")
    child = _node("child")
    root.children.append(child)
    child.parent = root
    canvas = GraphCanvas()
    canvas.load_graph(Graph(roots=[root]))
    assert root.id in canvas._items
    assert child.id in canvas._items


def test_canvas_select_node_emits_signal(qapp):
    root   = _node("root")
    canvas = GraphCanvas()
    canvas.load_graph(Graph(roots=[root]))
    received = []
    canvas.node_selected.connect(received.append)
    canvas.select_node(root.id)
    assert canvas._selected_id == root.id
    assert received == [root.id]


def test_canvas_find_node_recursive(qapp):
    child = _node("child")
    root  = _node("root")
    root.children.append(child)
    child.parent = root
    canvas = GraphCanvas()
    canvas.load_graph(Graph(roots=[root]))
    assert canvas._find_node(child.id) is child


from PySide6.QtCore import QPointF


def test_drop_refused_when_target_if_node_already_has_two_children(qapp):
    target  = _node("check", NodeType.IF)
    child_a = _node("true_branch")
    child_b = _node("false_branch")
    target.children = [child_a, child_b]
    child_a.parent = target
    child_b.parent = target
    drag = _node("extra")

    canvas = GraphCanvas()
    canvas.load_graph(Graph(roots=[target, drag]))
    canvas._drag_node_id = drag.id

    received = []
    canvas.drop_rejected.connect(received.append)
    target_pos = canvas._items[target.id].sceneBoundingRect().center()
    canvas._perform_drop(target_pos)

    assert target.children == [child_a, child_b]
    assert drag not in target.children
    assert drag in canvas._graph.roots
    assert received


def test_drop_allowed_when_target_if_node_has_one_child(qapp):
    target  = _node("check", NodeType.IF)
    child_a = _node("true_branch")
    target.children = [child_a]
    child_a.parent = target
    drag = _node("extra")

    canvas = GraphCanvas()
    canvas.load_graph(Graph(roots=[target, drag]))
    canvas._drag_node_id = drag.id

    received = []
    canvas.drop_rejected.connect(received.append)
    target_pos = canvas._items[target.id].sceneBoundingRect().center()
    canvas._perform_drop(target_pos)

    assert drag in target.children
    assert not received
