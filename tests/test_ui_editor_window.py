import uuid
from flower.models.node import Node, NodeType
from flower.ui.editor.editor_window import EditorWindow


def test_editor_window_node_id(qapp):
    node = Node(id=str(uuid.uuid4()), name="build", type=NodeType.NOOP)
    win = EditorWindow(node)
    assert win.node_id() == node.id


def test_editor_window_title(qapp):
    node = Node(id=str(uuid.uuid4()), name="build", type=NodeType.SCRIPT,
                type_data={"language": "bash", "body": ""})
    win = EditorWindow(node)
    assert "build" in win.windowTitle()


def test_editor_window_apply_emits_signal(qapp):
    node = Node(id=str(uuid.uuid4()), name="build", type=NodeType.NOOP)
    win  = EditorWindow(node)
    received = []
    win.node_updated.connect(lambda nid, n: received.append((nid, n)))
    win._apply()
    assert len(received) == 1
    assert received[0][0] == node.id
