import uuid
from PySide6.QtCore import QPointF, QPoint
from flower.engine.api import FlowGraph
from flower.engine.models.graph import Graph
from flower.engine.models.node import Node, NodeType
from flower.app.canvas import GraphCanvas


def _node(name, ntype=NodeType.NOOP):
    return Node(id=str(uuid.uuid4()), name=name, type=ntype)


def _canvas(*roots):
    flow   = FlowGraph(Graph(roots=list(roots)))
    canvas = GraphCanvas()
    canvas.set_flow(flow)
    return canvas, flow


def test_canvas_draws_every_node_of_the_flow(qapp):
    root  = _node("root")
    child = _node("child")
    root.children.append(child)
    child.parent = root

    canvas, _ = _canvas(root)

    assert root.id in canvas._items
    assert child.id in canvas._items


def test_canvas_select_node_emits_signal(qapp):
    root = _node("root")
    canvas, _ = _canvas(root)
    received = []
    canvas.node_selected.connect(received.append)

    canvas.select_node(root.id)

    assert canvas.selected_id == root.id
    assert received == [root.id]


def test_drop_refused_when_target_if_node_already_has_two_children(qapp):
    target  = _node("check", NodeType.IF)
    child_a = _node("true_branch")
    child_b = _node("false_branch")
    target.children = [child_a, child_b]
    child_a.parent = target
    child_b.parent = target
    drag = _node("extra")

    canvas, flow = _canvas(target, drag)
    canvas._drag_node_id = drag.id
    received = []
    canvas.drop_rejected.connect(received.append)

    canvas._perform_drop(canvas._items[target.id].sceneBoundingRect().center())

    assert target.children == [child_a, child_b]
    assert drag in flow.graph.roots
    assert received == ["Un nœud « if » ne peut avoir plus de 2 enfant(s)."]


def test_drop_onto_its_own_descendant_is_refused(qapp):
    grandparent = _node("grandparent")
    parent      = _node("parent")
    child       = _node("child")
    grandparent.children = [parent]
    parent.parent = grandparent
    parent.children = [child]
    child.parent = parent

    canvas, flow = _canvas(grandparent)
    canvas._drag_node_id = grandparent.id
    received = []
    canvas.drop_rejected.connect(received.append)

    canvas._perform_drop(canvas._items[child.id].sceneBoundingRect().center())

    assert grandparent.children == [parent]
    assert flow.graph.roots == [grandparent]
    assert received == ["Un nœud ne peut pas devenir son propre descendant."]


def test_drop_allowed_when_target_if_node_has_one_child(qapp):
    target  = _node("check", NodeType.IF)
    child_a = _node("true_branch")
    target.children = [child_a]
    child_a.parent = target
    drag = _node("extra")

    canvas, flow = _canvas(target, drag)
    canvas._drag_node_id = drag.id
    received = []
    canvas.drop_rejected.connect(received.append)

    canvas._perform_drop(canvas._items[target.id].sceneBoundingRect().center())

    assert drag in target.children
    assert not received


def test_drop_marks_the_flow_modified(qapp):
    target = _node("target")
    drag   = _node("drag")
    canvas, flow = _canvas(target, drag)
    canvas._drag_node_id = drag.id

    canvas._perform_drop(canvas._items[target.id].sceneBoundingRect().center())

    assert flow.is_dirty is True


def test_reorder_marks_the_flow_modified(qapp):
    first  = _node("first")
    second = _node("second")
    canvas, flow = _canvas(first, second)
    canvas.select_node(second.id)

    canvas._reorder_sibling(second, -1)

    assert flow.graph.roots == [second, first]
    assert flow.is_dirty is True


def _executable_node(name="build"):
    return Node(
        id=str(uuid.uuid4()), name=name, type=NodeType.SCRIPT,
        type_data={"language": "sh", "body": ""}, is_executable=True,
    )


def test_canvas_relays_node_exec_requested(qapp):
    node = _executable_node()
    canvas, _ = _canvas(node)
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
    node = _executable_node()
    canvas, _ = _canvas(node)
    rect = canvas._items[node.id].sceneBoundingRect()
    canvas._arm_drag_candidate(
        QPointF(rect.right() - 28.0, rect.center().y()), QPoint(0, 0)
    )
    assert canvas._drag_candidate_id is None


def test_press_on_the_node_body_still_arms_a_drag(qapp):
    node = _executable_node()
    canvas, _ = _canvas(node)
    rect = canvas._items[node.id].sceneBoundingRect()
    canvas._arm_drag_candidate(
        QPointF(rect.left() + 60.0, rect.center().y()), QPoint(0, 0)
    )
    assert canvas._drag_candidate_id == node.id
