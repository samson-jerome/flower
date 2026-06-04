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
