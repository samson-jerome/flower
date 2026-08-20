import uuid
from flower.models.graph import Graph
from flower.models.node import Node, NodeType
from flower.ui import main_window as main_window_module
from flower.ui.main_window import MainWindow


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
        main_window_module, "launch_in_terminal",
        lambda script_path: (launched.append(script_path), True)[1],
    )
    win = MainWindow()
    win._graph = graph
    win._path  = flow_path
    win._canvas.load_graph(graph)
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


def test_exec_node_ignores_an_unknown_id(qapp, tmp_path, monkeypatch):
    node = _script_node("build", executable=True)
    win, launched = _window(Graph(roots=[node]), tmp_path / "demo.flow", monkeypatch)

    win._exec_node("no-such-id")

    assert launched == []
