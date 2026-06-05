import uuid
import pytest
from flower.models.node import Node, NodeType
from flower.ui.editor.node_form import NodeForm
from flower.ui.dock_panel import DockPanel


def _node(name="alpha"):
    return Node(id=str(uuid.uuid4()), name=name, type=NodeType.NOOP)


def _form(node):
    return NodeForm(node)


def test_dock_adds_entry(qapp):
    panel = DockPanel()
    node = _node()
    form = _form(node)
    panel.dock(node.id, node, form)
    assert node.id in panel._entries


def test_dock_same_node_twice_is_noop(qapp):
    panel = DockPanel()
    node = _node()
    form = _form(node)
    panel.dock(node.id, node, form)
    panel.dock(node.id, node, form)  # second call ignored
    assert len(panel._entries) == 1


def test_undock_removes_entry_and_returns_form(qapp):
    panel = DockPanel()
    node = _node()
    form = _form(node)
    panel.dock(node.id, node, form)
    returned = panel.undock(node.id)
    assert returned is form
    assert node.id not in panel._entries


def test_remove_destroys_entry(qapp):
    panel = DockPanel()
    node = _node()
    form = _form(node)
    panel.dock(node.id, node, form)
    panel.remove(node.id)
    assert node.id not in panel._entries


def test_clear_removes_all_entries(qapp):
    panel = DockPanel()
    for name in ["a", "b", "c"]:
        node = _node(name)
        panel.dock(node.id, node, _form(node))
    panel.clear()
    assert len(panel._entries) == 0


def test_close_requested_signal(qapp):
    panel = DockPanel()
    node = _node()
    panel.dock(node.id, node, _form(node))
    received = []
    panel.close_requested.connect(received.append)
    panel._entries[node.id]._close_btn.click()
    assert received == [node.id]


def test_undock_requested_signal(qapp):
    panel = DockPanel()
    node = _node()
    panel.dock(node.id, node, _form(node))
    received = []
    panel.undock_requested.connect(received.append)
    panel._entries[node.id]._undock_btn.click()
    assert received == [node.id]


def test_name_changed_signal(qapp):
    panel = DockPanel()
    node = _node("alpha")
    panel.dock(node.id, node, _form(node))
    received = []
    panel.name_changed.connect(lambda nid, name: received.append((nid, name)))
    entry = panel._entries[node.id]
    entry._name_edit.setText("beta")
    entry._name_edit.editingFinished.emit()
    assert received == [(node.id, "beta")]


def test_collapse_toggle_hides_body(qapp):
    panel = DockPanel()
    panel.show()
    node = _node()
    panel.dock(node.id, node, _form(node))
    entry = panel._entries[node.id]
    assert entry._body.isVisible()
    entry._toggle_btn.click()
    assert not entry._body.isVisible()
    entry._toggle_btn.click()
    assert entry._body.isVisible()
