import uuid
from flower.models.node import Node, NodeType
from flower.layout.tree_layout import NodePos
from flower.ui.node_item import NodeItem, NodeItemSignals, NODE_HEIGHT
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
