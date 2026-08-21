import uuid
from flower.engine import api as api_module
from flower.engine.api import FlowGraph
from flower.engine.models.graph import Graph
from flower.engine.models.node import Node, NodeType
from flower.app.main_window import MainWindow


def _script_node(name, executable=False, active=True):
    return Node(
        id=str(uuid.uuid4()), name=name, type=NodeType.SCRIPT,
        type_data={"language": "bash", "body": ""},
        is_executable=executable, is_active=active,
    )


def _link(parent, children):
    parent.children = children
    for child in children:
        child.parent = parent
    return parent


def _window(graph, flow_path, monkeypatch):
    """MainWindow wired to `graph` with the terminal launcher stubbed out, so a
    test never spawns a process. Returns the window and the list the stub
    appends every launched script path to."""
    launched = []
    monkeypatch.setattr(
        api_module, "run_script",
        lambda script_path, terminal=None: (launched.append(script_path), True)[1],
    )
    win = MainWindow()
    win._load(FlowGraph(graph, flow_path))
    return win, launched


def test_exec_node_launches_a_script_truncated_after_the_target(qapp, tmp_path, monkeypatch):
    target = _link(_script_node("target", executable=True), [_script_node("child")])
    root   = _link(_script_node("root"), [target, _script_node("after")])
    win, launched = _window(Graph(roots=[root]), tmp_path / "demo.flow", monkeypatch)

    win._exec_node(target.id)

    assert len(launched) == 1
    script = launched[0]
    assert script.name.startswith("demo_target_")
    text = script.read_text()
    assert "FL_NODE_NAME='root'"   in text
    assert "FL_NODE_NAME='target'" in text
    assert "FL_NODE_NAME='child'"  not in text
    assert "FL_NODE_NAME='after'"  not in text


def test_exec_node_ignores_a_node_that_is_not_executable(qapp, tmp_path, monkeypatch):
    node = _script_node("plain")
    win, launched = _window(Graph(roots=[node]), tmp_path / "demo.flow", monkeypatch)

    win._exec_node(node.id)

    assert launched == []
    assert list(tmp_path.iterdir()) == []


def test_exec_node_ignores_an_inactive_node(qapp, tmp_path, monkeypatch):
    node = _script_node("build", executable=True, active=False)
    win, launched = _window(Graph(roots=[node]), tmp_path / "demo.flow", monkeypatch)

    win._exec_node(node.id)

    assert launched == []
    assert list(tmp_path.iterdir()) == []


def test_exec_node_ignores_an_active_node_under_an_inactive_ancestor(qapp, tmp_path, monkeypatch):
    # Not reachable through canvas._on_active_toggled() (which repairs the
    # subtree), but NodeForm.apply_to_node() can write is_active directly.
    target = _link(_script_node("target", executable=True), [])
    root   = _link(_script_node("root", active=False), [target])
    win, launched = _window(Graph(roots=[root]), tmp_path / "demo.flow", monkeypatch)

    win._exec_node(target.id)

    assert launched == []
    assert list(tmp_path.iterdir()) == []
    assert win.statusBar().currentMessage() == "Un nœud parent est inactif : rien à exécuter."


def test_exec_node_ignores_an_unknown_id(qapp, tmp_path, monkeypatch):
    node = _script_node("build", executable=True)
    win, launched = _window(Graph(roots=[node]), tmp_path / "demo.flow", monkeypatch)

    win._exec_node("no-such-id")

    assert launched == []


def test_canvas_exec_signal_reaches_exec_node(qapp, tmp_path, monkeypatch):
    node = _script_node("build", executable=True)
    win, launched = _window(Graph(roots=[node]), tmp_path / "demo.flow", monkeypatch)

    win._canvas.node_exec_requested.emit(node.id)
    qapp.processEvents()  # the signal chain behind node_exec_requested is queued

    assert len(launched) == 1


def test_editor_exec_button_reaches_exec_node(qapp, tmp_path, monkeypatch):
    node = _script_node("build", executable=True)
    win, launched = _window(Graph(roots=[node]), tmp_path / "demo.flow", monkeypatch)

    win._open_editor(node.id)
    win._editor_windows[node.id]._exec_btn.click()

    assert len(launched) == 1
