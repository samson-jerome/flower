import uuid
from flower.engine.models.node import Node, NodeType
from flower.engine.models.graph import Graph
from flower.app.canvas import GraphCanvas


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


from PySide6.QtCore import QPoint


def _executable_node(name="build"):
    return Node(
        id=str(uuid.uuid4()), name=name, type=NodeType.SCRIPT,
        type_data={"language": "sh", "body": ""}, is_executable=True,
    )


def test_canvas_relays_node_exec_requested(qapp):
    node   = _executable_node()
    canvas = GraphCanvas()
    canvas.load_graph(Graph(roots=[node]))
    received = []
    canvas.node_exec_requested.connect(received.append)
    canvas._signals.exec_requested.emit(node.id)
    # Nothing must arrive synchronously: the receiver opens a modal dialog and
    # starts a process, which must not happen while the graphics item's mouse
    # event is still on the stack. This assertion is what would catch a
    # future refactor to a direct connection -- a direct connection would
    # already have delivered by this point.
    assert received == []
    # The connection is queued on purpose, so delivery needs one event loop
    # turn: the receiver may open a modal dialog and start a process.
    qapp.processEvents()
    assert received == [node.id]


def test_press_on_the_exec_pill_does_not_arm_a_drag(qapp):
    node   = _executable_node()
    canvas = GraphCanvas()
    canvas.load_graph(Graph(roots=[node]))
    rect = canvas._items[node.id].sceneBoundingRect()
    canvas._arm_drag_candidate(
        QPointF(rect.right() - 28.0, rect.center().y()), QPoint(0, 0)
    )
    assert canvas._drag_candidate_id is None


def test_press_on_the_node_body_still_arms_a_drag(qapp):
    node   = _executable_node()
    canvas = GraphCanvas()
    canvas.load_graph(Graph(roots=[node]))
    rect = canvas._items[node.id].sceneBoundingRect()
    canvas._arm_drag_candidate(
        QPointF(rect.left() + 60.0, rect.center().y()), QPoint(0, 0)
    )
    assert canvas._drag_candidate_id == node.id
