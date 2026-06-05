import uuid
from flower.models.node import Node, NodeType
from flower.ui.editor.editor_window import EditorWindow
from flower.ui.editor.node_form import NodeForm


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


def test_extract_form_returns_nodeform(qapp):
    node = Node(id=str(uuid.uuid4()), name="x", type=NodeType.NOOP)
    win = EditorWindow(node)
    form = win.extract_form()
    assert isinstance(form, NodeForm)


def test_extract_form_reparents_form(qapp):
    node = Node(id=str(uuid.uuid4()), name="x", type=NodeType.NOOP)
    win = EditorWindow(node)
    form = win.extract_form()
    # After extraction the form has no parent (ready for reparenting).
    assert form.parent() is None


def test_dock_requested_signal(qapp):
    node = Node(id=str(uuid.uuid4()), name="x", type=NodeType.NOOP)
    win = EditorWindow(node)
    received = []
    win.dock_requested.connect(received.append)
    win._dock_btn.click()
    assert received == [node.id]


def test_editor_window_with_existing_form(qapp):
    node = Node(id=str(uuid.uuid4()), name="y", type=NodeType.NOOP)
    existing_form = NodeForm(node)
    win = EditorWindow(node, form=existing_form)
    assert win._form is existing_form
