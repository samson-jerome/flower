import uuid
from flower.engine.models.node import Node, NodeType
from flower.app.layout.tree_layout import (
    compute_layout, node_label, NODE_STEP, MIN_NODE_WIDTH, MAX_NODE_WIDTH,
    NODE_PADDING_H, EXEC_BTN_W, EXEC_ZONE_W,
)


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


def test_label_loop_expression():
    n = _node("iter", NodeType.LOOP, type_data={"index": "f", "mode": "expression"})
    assert node_label(n) == "iter [f: expr]"


def test_label_loop_unknown_mode_falls_back_to_range():
    # Aligned with the generator and the editor, which both treat an
    # unrecognized mode as range.
    n = _node("iter", NodeType.LOOP, type_data={
        "index": "i", "mode": "legacy", "start": 0, "end": 3,
    })
    assert node_label(n) == "iter [i: 0..3]"


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


def test_exec_zone_is_the_pill_plus_its_gap():
    assert EXEC_ZONE_W == EXEC_BTN_W + 6.0


def test_column_width_reserves_room_for_the_exec_pill():
    node = _node("build", NodeType.SCRIPT, type_data={"language": "sh"})
    # label "build [sh]" -> 10 * 8 = 80 px avec le width_fn de ce fichier
    assert compute_layout([node], width_fn)[node.id].width == MIN_NODE_WIDTH
    node.is_executable = True
    assert (
        compute_layout([node], width_fn)[node.id].width
        == 80.0 + NODE_PADDING_H + EXEC_ZONE_W
    )


def test_column_width_ignores_the_flag_on_an_ineligible_type():
    node = _node("check", NodeType.IF, type_data={"condition": "x"})
    node.is_executable = True
    assert compute_layout([node], width_fn)[node.id].width == MIN_NODE_WIDTH


def test_column_width_stays_capped_with_the_exec_pill():
    node = _node("x" * 60, NodeType.SCRIPT)
    node.is_executable = True
    assert compute_layout([node], width_fn)[node.id].width == MAX_NODE_WIDTH
