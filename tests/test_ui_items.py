import uuid
from PySide6.QtWidgets import QGraphicsSceneMouseEvent
from PySide6.QtCore import QEvent, QPointF, Qt
from flower.models.node import Node, NodeType
from flower.layout.tree_layout import NodePos, EXEC_BTN_W, EXEC_ZONE_W
from flower.ui.node_item import NodeItem, NodeItemSignals, NodeZone, NODE_HEIGHT
from flower.ui.edge_item import EdgeItem


def _node(name, ntype=NodeType.NOOP):
    return Node(id=str(uuid.uuid4()), name=name, type=ntype)


def test_node_item_bounding_rect(qapp):
    node    = _node("hello")
    pos     = NodePos(x=0, y=0, width=150)
    signals = NodeItemSignals()
    item    = NodeItem(node, pos, signals)
    r = item.boundingRect()
    assert r.width() == 150
    assert r.height() == NODE_HEIGHT


def test_node_item_select(qapp):
    node    = _node("hello")
    signals = NodeItemSignals()
    item    = NodeItem(node, NodePos(0, 0, 150), signals)
    item.set_selected(True)
    assert item._selected is True


def test_edge_item_created(qapp):
    p_pos = NodePos(0, 0, 150)
    c_pos = NodePos(160, 44, 150)
    edge  = EdgeItem(p_pos, c_pos, child_index=0, parent_type=NodeType.NOOP)
    assert edge is not None


def test_edge_if_has_label(qapp):
    p_pos = NodePos(0, 0, 150)
    c_pos = NodePos(160, 44, 150)
    edge  = EdgeItem(p_pos, c_pos, child_index=0, parent_type=NodeType.IF)
    assert len(edge.childItems()) == 1


def _exec_item(width=200.0, children=0, active=True, executable=True):
    """NodeItem for a script node, optionally marked executable. Width 200
    puts the pill at [152, 192] without children, [132, 172] with."""
    node = Node(
        id=str(uuid.uuid4()), name="build", type=NodeType.SCRIPT,
        type_data={"language": "sh", "body": ""},
        is_executable=executable, is_active=active,
    )
    for i in range(children):
        child = Node(id=str(uuid.uuid4()), name=f"c{i}", type=NodeType.NOOP, parent=node)
        node.children.append(child)
    signals = NodeItemSignals()
    return NodeItem(node, NodePos(0, 0, width), signals), node, signals


def _mouse_event(kind, x):
    event = QGraphicsSceneMouseEvent(kind)
    event.setPos(QPointF(x, NODE_HEIGHT / 2))
    event.setButton(Qt.MouseButton.LeftButton)
    return event


def test_zone_at_without_children(qapp):
    item, _, _ = _exec_item()
    assert item.zone_at(10.0)  == NodeZone.ACTIVE
    assert item.zone_at(100.0) == NodeZone.BODY
    assert item.zone_at(152.0) == NodeZone.EXEC
    assert item.zone_at(192.0) == NodeZone.EXEC
    assert item.zone_at(196.0) == NodeZone.BODY


def test_zone_at_with_children_keeps_the_collapse_button_in_place(qapp):
    item, _, _ = _exec_item(children=1)
    assert item.zone_at(180.0) == NodeZone.COLLAPSE
    assert item.zone_at(132.0) == NodeZone.EXEC
    assert item.zone_at(172.0) == NodeZone.EXEC
    assert item.zone_at(100.0) == NodeZone.BODY


def test_a_non_executable_node_has_no_exec_zone(qapp):
    item, _, _ = _exec_item(executable=False)
    assert item._exec_rect() is None
    assert item.zone_at(160.0) == NodeZone.BODY


def test_press_on_the_exec_pill_emits_exec_requested(qapp):
    item, node, signals = _exec_item()
    received = []
    signals.exec_requested.connect(received.append)
    item.mousePressEvent(_mouse_event(QEvent.Type.GraphicsSceneMousePress, 160.0))
    assert received == [node.id]


def test_press_on_the_exec_pill_of_an_inactive_node_emits_nothing(qapp):
    item, _, signals = _exec_item(active=False)
    received = []
    signals.exec_requested.connect(received.append)
    signals.selected.connect(received.append)
    item.mousePressEvent(_mouse_event(QEvent.Type.GraphicsSceneMousePress, 160.0))
    assert received == []


def test_double_click_on_the_exec_pill_does_not_open_the_editor(qapp):
    item, _, signals = _exec_item()
    received = []
    signals.edit_requested.connect(received.append)
    item.mouseDoubleClickEvent(
        _mouse_event(QEvent.Type.GraphicsSceneMouseDoubleClick, 160.0)
    )
    assert received == []


def test_double_click_on_the_body_still_opens_the_editor(qapp):
    item, node, signals = _exec_item()
    received = []
    signals.edit_requested.connect(received.append)
    item.mouseDoubleClickEvent(
        _mouse_event(QEvent.Type.GraphicsSceneMouseDoubleClick, 100.0)
    )
    assert received == [node.id]


def test_press_on_the_body_still_selects(qapp):
    item, node, signals = _exec_item()
    received = []
    signals.selected.connect(received.append)
    item.mousePressEvent(_mouse_event(QEvent.Type.GraphicsSceneMousePress, 100.0))
    assert received == [node.id]


def test_label_leaves_the_same_gap_before_the_pill_with_and_without_children(qapp):
    without_children, _, _ = _exec_item(children=0)
    with_children, _, _    = _exec_item(children=1)

    gap_without = without_children._exec_rect().left() - without_children._label_rect().right()
    gap_with    = with_children._exec_rect().left() - with_children._label_rect().right()
    expected_gap = EXEC_ZONE_W - EXEC_BTN_W  # the margin reserved after the pill itself

    assert gap_without == expected_gap
    assert gap_with == expected_gap


def test_press_on_the_activity_dot_still_toggles(qapp):
    item, node, signals = _exec_item()
    received = []
    signals.active_toggled.connect(received.append)
    item.mousePressEvent(_mouse_event(QEvent.Type.GraphicsSceneMousePress, 10.0))
    assert received == [node.id]
