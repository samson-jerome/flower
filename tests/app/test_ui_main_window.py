from pathlib import Path
import uuid
from PySide6.QtWidgets import QMessageBox
from flower.engine import api as api_module
from flower.engine.api import FlowGraph
from flower.engine.models.graph import Graph
from flower.engine.models.node import Node, NodeType
from flower.app.main_window import MainWindow
from flower.version import get_version


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


def test_add_child_node_falls_back_to_a_root_on_a_stale_selection(qapp, tmp_path, monkeypatch):
    """_delete_selected_node() never clears canvas.selected_id, so the id it
    leaves selected is stale as soon as the node is gone. Calling the method
    directly (not through the add_child_requested signal) makes a regression
    here fail outright instead of the ValueError from FlowGraph.add_node()
    being swallowed somewhere upstream."""
    node = _script_node("solo")
    win, _ = _window(Graph(roots=[node]), tmp_path / "demo.flow", monkeypatch)
    win._canvas.select_node(node.id)

    win._delete_selected_node()
    win._add_child_node()

    assert len(win._flow.graph.roots) == 1
    assert win._flow.graph.roots[0].parent is None


def test_the_about_box_shows_the_version(qapp, tmp_path, monkeypatch):
    """The About box is where someone looks for the version in a windowed
    application launched from a desktop shortcut, with no terminal in sight.

    Goes through the "Aide" menu's "À propos de Flower" action rather than
    calling _show_about() directly, so this protects the full path from the
    menu entry to the handler, not just the handler in isolation. The two
    next() calls look the menu and action up by label, not by position, and
    raise StopIteration outright if either is missing or mislabeled."""
    shown = []
    monkeypatch.setattr(
        QMessageBox, "about",
        staticmethod(lambda parent, title, text: shown.append(text)),
    )
    win, _ = _window(Graph(), tmp_path / "demo.flow", monkeypatch)

    # Building help_menu in two steps (rather than chaining a.menu() straight
    # into the generator expression) keeps a live Python reference to the
    # QAction throughout the lookup — PySide/Shiboken has been observed to
    # free the underlying QMenu prematurely otherwise.
    menu_bar_actions = win.menuBar().actions()
    help_action = next(a for a in menu_bar_actions if a.text() == "Aide")
    help_menu = help_action.menu()
    about = next(a for a in help_menu.actions() if a.text() == "À propos de Flower")

    about.trigger()

    assert len(shown) == 1
    assert get_version() in shown[0]
    assert "Flower" in shown[0]


def test_the_terminal_action_opens_the_flow_folder(qapp, tmp_path, monkeypatch):
    """Goes through the "Exécution" menu action, so the shortcut's whole path
    from the menu entry to the runner is protected, not just the handler."""
    opened = []
    monkeypatch.setattr(
        api_module, "open_terminal",
        lambda directory, terminal: (opened.append((directory, terminal)), True)[1],
    )
    # The handler reads the real QSettings otherwise, so a developer with a
    # saved Terminal preference would fail this test.
    monkeypatch.setattr(
        "flower.app.main_window.load_terminal", lambda: "x-terminal-emulator"
    )
    win, _ = _window(Graph(), tmp_path / "demo.flow", monkeypatch)

    menu_bar_actions = win.menuBar().actions()
    exec_action = next(a for a in menu_bar_actions if a.text() == "Exécution")
    exec_menu = exec_action.menu()
    terminal_entry = next(
        a for a in exec_menu.actions() if a.text() == "Ouvrir un terminal ici"
    )

    terminal_entry.trigger()

    assert opened == [(tmp_path, "x-terminal-emulator")]


def test_the_terminal_action_needs_no_saved_file(qapp, tmp_path, monkeypatch):
    """The unsaved case is the point of the shortcut: it must not pop the
    "Sauver sous" dialog, which would block the test."""
    opened = []
    monkeypatch.setattr(
        api_module, "open_terminal",
        lambda directory, terminal: (opened.append(directory), True)[1],
    )
    monkeypatch.setattr(
        "flower.app.main_window.load_terminal", lambda: "x-terminal-emulator"
    )
    monkeypatch.chdir(tmp_path)
    win, _ = _window(Graph(), None, monkeypatch)

    win._open_terminal()

    assert opened == [Path.cwd()]
