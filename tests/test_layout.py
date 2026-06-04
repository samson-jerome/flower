import uuid
from flower.models.node import Node, NodeType
from flower.layout.tree_layout import compute_layout, node_label, NODE_STEP, MIN_NODE_WIDTH


def _node(name, ntype=NodeType.NOOP, children=None, type_data=None):
    return Node(
        id=str(uuid.uuid4()), name=name, type=ntype,
        children=children or [], type_data=type_data or {},
    )


width_fn = lambda s: len(s) * 8  # approximation fixe, sans Qt


def test_label_noop():
    assert node_label(_node("hello")) == "hello"


def test_label_script_with_language():
    n = _node("build", NodeType.SCRIPT, type_data={"language": "bash"})
    assert node_label(n) == "build [bash]"


def test_label_script_no_language():
    n = _node("build", NodeType.SCRIPT)
    assert node_label(n) == "build"


def test_label_if():
    n = _node("check", NodeType.IF, type_data={"condition": "x > 0"})
    assert node_label(n) == "check : x > 0"


def test_label_loop_range():
    n = _node("iter", NodeType.LOOP, type_data={"index": "i", "mode": "range", "start": 0, "end": 10})
    assert node_label(n) == "iter [i: 0..10]"


def test_label_loop_list():
    n = _node("iter", NodeType.LOOP, type_data={"index": "item", "mode": "list"})
    assert node_label(n) == "iter [item: list]"


def test_layout_single_root():
    root = _node("root")
    positions = compute_layout([root], width_fn)
    assert root.id in positions
    p = positions[root.id]
    assert p.x == 0.0
    assert p.y == 0.0


def test_layout_child_is_to_the_right():
    child = _node("child")
    root  = _node("root", children=[child])
    child.parent = root
    positions = compute_layout([root], width_fn)
    assert positions[child.id].x > positions[root.id].x


def test_layout_child_y_offset():
    child = _node("child")
    root  = _node("root", children=[child])
    child.parent = root
    positions = compute_layout([root], width_fn)
    # First child aligns vertically with its parent.
    assert positions[child.id].y == positions[root.id].y


def test_layout_two_roots_stacked():
    r1 = _node("r1")
    r2 = _node("r2")
    positions = compute_layout([r1, r2], width_fn)
    assert positions[r1.id].y == 0.0
    assert positions[r2.id].y == NODE_STEP
