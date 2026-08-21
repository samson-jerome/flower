from __future__ import annotations
import uuid
from pathlib import Path
from datetime import datetime, timezone
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QMessageBox, QFileDialog, QLabel, QApplication,
)
from PySide6.QtCore import Qt, QSettings
from flower.engine.models.graph import Graph
from flower.engine.models.node import Node, NodeType, MAX_CHILDREN, can_exec
from flower.app.canvas import GraphCanvas
from flower.app.toolbar import ToolBar
from flower.app.dock_panel import DockPanel
from flower.app.notes_panel import NotesPanel, bind_notes_to_splitter
from flower.app.vars_panel import VarsPanel
from flower.app.editor.editor_window import EditorWindow
from flower.app.preferences_dialog import PreferencesDialog
from flower.app.theme import is_dark
from flower.engine.io.xml_writer import write_flow
from flower.engine.io.xml_reader import read_flow
from flower.app.interpreters import load_interpreters
from flower.engine.execution.bash_generator import write_bash_script, write_timestamped_bash_script
from flower.engine.execution.runner import run_script
from flower.engine.execution.traversal import prune_to_node

# (background, text) pairs, keyed by whether the app is currently dark.
# Same palette as flower.app.editor.node_form, for visual consistency between
# the main window's global panels and the node dialog's local ones.
_DESCRIPTION_COLORS = {
    True:  ("#898989", "#F0F0F0"),   # gris souris
    False: ("#D8D8D8", "#2B2B2B"),   # gris souris clair
}
_VARIABLES_COLORS = {
    True:  ("#2E5F66", "#F0F0F0"),   # bleu pétrole
    False: ("#CFE6E9", "#1B3A40"),   # bleu pétrole clair
}


def _collect_names(graph: Graph) -> set[str]:
    names: set[str] = set()
    def _walk(nodes: list[Node]) -> None:
        for n in nodes:
            names.add(n.name)
            _walk(n.children)
    _walk(graph.roots)
    return names


def _unique_name(base: str, graph: Graph) -> str:
    existing = _collect_names(graph)
    if base not in existing:
        return base
    i = 1
    while f"{base}_{i}" in existing:
        i += 1
    return f"{base}_{i}"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flower")
        self.resize(1100, 700)

        self._graph:           Graph                     = Graph()
        self._path:            Path | None               = None
        self._dirty:           bool                      = False
        self._editor_windows:  dict[str, EditorWindow]   = {}

        self._toolbar     = ToolBar(self)
        self._canvas      = GraphCanvas()
        self._dock_panel  = DockPanel()
        self._notes       = NotesPanel(title="Description")
        self._notes.text_changed.connect(self._on_notes_changed)
        self._global_vars = VarsPanel(title="Variables globales")
        self._global_vars.variables_changed.connect(self._on_global_vars_changed)

        self._apply_theme_colors()
        app = QApplication.instance()
        if app is not None:
            app.paletteChanged.connect(self._apply_theme_colors)

        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self._toolbar)

        notes_canvas = QSplitter(Qt.Orientation.Vertical)
        notes_canvas.addWidget(self._notes)
        notes_canvas.addWidget(self._global_vars)
        notes_canvas.addWidget(self._canvas)
        notes_canvas.setStretchFactor(0, 0)
        notes_canvas.setStretchFactor(1, 0)
        notes_canvas.setStretchFactor(2, 1)
        notes_canvas.setSizes([120, 160, 580])
        bind_notes_to_splitter(self._notes, notes_canvas, index=0)
        bind_notes_to_splitter(self._global_vars, notes_canvas, index=1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(notes_canvas)
        splitter.addWidget(self._dock_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([800, 300])
        self.setCentralWidget(splitter)

        self._status_node_label = QLabel()
        self.statusBar().addWidget(self._status_node_label)

        self._build_menu()
        self._connect_signals()
        self._canvas.load_graph(self._graph)
        self._sync_notes_from_graph()
        self._sync_vars_from_graph()

    # ── Menu ────────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Fichier")
        file_menu.addAction("Nouveau",       self._new_file,  "Ctrl+N")
        file_menu.addAction("Ouvrir…",       self._open_file, "Ctrl+O")
        self._recent_menu = file_menu.addMenu("Ouvrir récents")
        self._refresh_recent_menu()
        file_menu.addAction("Sauver",        self._save_file, "Ctrl+S")
        file_menu.addAction("Sauver sous…",  self._save_as,   "Ctrl+Shift+S")
        file_menu.addSeparator()
        file_menu.addAction("Préférences…",  self._open_preferences)
        file_menu.addSeparator()
        file_menu.addAction("Quitter",       self.close,      "Ctrl+Q")

        exec_menu = self.menuBar().addMenu("Exécution")
        exec_menu.addAction("Générer le script", self._generate_script)
        exec_menu.addAction("Lancer le script",  self._launch_script, "Alt+R")

    def _open_preferences(self) -> None:
        PreferencesDialog(self).exec()

    def _connect_signals(self) -> None:
        self._canvas.node_selected.connect(self._on_node_selected)
        self._canvas.node_edit_requested.connect(self._open_editor)
        self._canvas.add_child_requested.connect(self._add_child_node)
        self._canvas.delete_requested.connect(self._delete_selected_node)
        self._canvas.node_active_changed.connect(self.mark_dirty)
        self._canvas.drop_rejected.connect(lambda msg: self.statusBar().showMessage(msg, 3000))
        self._canvas.node_exec_requested.connect(self._exec_node)
        self._toolbar.add_node_requested.connect(self._add_child_node)
        self._toolbar.delete_node_requested.connect(self._delete_selected_node)
        self._toolbar.refresh_requested.connect(self._canvas.refresh_layout)
        self._toolbar.export_requested.connect(self._save_as)
        self._dock_panel.undock_requested.connect(self._on_undock_requested)
        self._dock_panel.close_requested.connect(self._on_dock_close_requested)
        self._dock_panel.name_changed.connect(self._on_name_changed)

    # ── File operations ─────────────────────────────────────────────────────

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        r = QMessageBox.question(
            self, "Modifications non sauvegardées",
            "Des modifications non sauvegardées seront perdues. Continuer ?",
        )
        return r == QMessageBox.StandardButton.Yes

    def _new_file(self) -> None:
        if not self._confirm_discard():
            return
        self._graph = Graph()
        self._path  = None
        self._dirty = False
        self._close_all_editors()
        self._dock_panel.clear()
        self._canvas.load_graph(self._graph)
        self._sync_notes_from_graph()
        self._sync_vars_from_graph()
        self._status_node_label.clear()
        self._update_title()

    def _open_file(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir", "", "Flow files (*.flow)")
        if not path:
            return
        self._open_path(Path(path))

    def _open_path(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "Fichier introuvable", f"Le fichier n'existe plus :\n{path}")
            self._remove_recent(path)
            return
        self._graph = read_flow(path)
        self._path  = path
        self._dirty = False
        self._close_all_editors()
        self._dock_panel.clear()
        self._canvas.load_graph(self._graph)
        self._sync_notes_from_graph()
        self._sync_vars_from_graph()
        self._status_node_label.clear()
        self._update_title()
        self._add_recent(path)

    def _save_file(self) -> None:
        if self._path is None:
            self._save_as()
            return
        self._graph.updated_at = datetime.now(timezone.utc).isoformat()
        write_flow(self._graph, self._path)
        self._dirty = False
        self._update_title()
        self.statusBar().showMessage("Fichier sauvegardé", 3000)
        self._add_recent(self._path)

    def _save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Sauver sous", "", "Flow files (*.flow)")
        if not path:
            return
        self._path = Path(path if path.endswith(".flow") else path + ".flow")
        self._save_file()

    def _generate_script(self) -> None:
        if self._path is None:
            self._save_as()
            if self._path is None:  # user cancelled the save dialog
                return
        write_bash_script(self._graph, self._path, interpreters=load_interpreters())
        self.statusBar().showMessage(
            f"Script généré : {self._path.with_suffix('.sh').name}", 3000
        )

    def _launch_script(self) -> None:
        if self._path is None:
            self._save_as()
            if self._path is None:  # user cancelled the save dialog
                return
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        script_path = write_timestamped_bash_script(
            self._graph, self._path, timestamp, interpreters=load_interpreters()
        )
        if run_script(script_path):
            self.statusBar().showMessage(f"Script lancé : {script_path.name}", 3000)
        else:
            QMessageBox.warning(
                self, "Échec du lancement",
                f"Impossible d'ouvrir un terminal pour exécuter {script_path.name}.",
            )

    def _exec_node(self, node_id: str) -> None:
        """Run the graph up to `node_id` included: generate the pruned script
        next to the .flow file, then open it in a terminal. Same guards as
        _launch_script(), plus the node's own eligibility -- both call sites
        filter already, but this is the only place that starts an execution and
        has to be safe on its own."""
        node = self._canvas._find_node(node_id)
        if node is None or not can_exec(node) or not node.is_active:
            return
        # NodeForm.apply_to_node() writes is_active straight into the node
        # with no ancestor repair (unlike canvas._on_active_toggled()), so an
        # active node under an inactive ancestor is reachable from the editor.
        # The generator drops the whole subtree at an inactive ancestor, so
        # without this guard the script would hold nothing but boilerplate
        # while the status bar reports success.
        ancestor = node.parent
        while ancestor is not None:
            if not ancestor.is_active:
                self.statusBar().showMessage("Un nœud parent est inactif : rien à exécuter.", 3000)
                return
            ancestor = ancestor.parent
        if self._path is None:
            self._save_as()
            if self._path is None:  # user cancelled the save dialog
                return
        script_path = write_timestamped_bash_script(
            prune_to_node(self._graph, node_id), self._path,
            datetime.now().strftime("%Y%m%d-%H%M%S"),
            interpreters=load_interpreters(), label=node.name,
        )
        if run_script(script_path):
            self.statusBar().showMessage(f"Exécution partielle : {script_path.name}", 3000)
        else:
            QMessageBox.warning(
                self, "Échec du lancement",
                f"Impossible d'ouvrir un terminal pour exécuter {script_path.name}.",
            )

    # ── Node operations ─────────────────────────────────────────────────────

    def _add_child_node(self) -> None:
        parent_id = self._canvas._selected_id
        parent = self._canvas._find_node(parent_id) if parent_id else None
        if parent is not None:
            max_children = MAX_CHILDREN.get(parent.type)
            if max_children is not None and len(parent.children) >= max_children:
                self.statusBar().showMessage(
                    f"Un nœud « {parent.type.value} » ne peut avoir plus de "
                    f"{max_children} enfant(s).",
                    3000,
                )
                return
        new_node = Node(id=str(uuid.uuid4()), name=_unique_name("nouveau", self._graph), type=NodeType.NOOP)
        if parent is not None:
            new_node.parent = parent
            parent.children.append(new_node)
        else:
            self._graph.roots.append(new_node)
        self.mark_dirty()
        self._canvas.refresh_layout()
        if parent_id:
            self._canvas.select_node(parent_id)

    def _delete_selected_node(self) -> None:
        node_id = self._canvas._selected_id
        if node_id is None:
            return
        node = self._canvas._find_node(node_id)
        if node is None:
            return
        if node.parent:
            node.parent.children.remove(node)
        elif node in self._graph.roots:
            self._graph.roots.remove(node)
        self._close_editor(node_id)
        self._dock_panel.remove(node_id)
        self.mark_dirty()
        self._canvas.refresh_layout()
        self._status_node_label.clear()
        self.statusBar().showMessage("Nœud supprimé", 3000)

    # ── Editor windows ───────────────────────────────────────────────────────

    def _open_editor(self, node_id: str) -> None:
        if node_id in self._editor_windows and not self._editor_windows[node_id].isVisible():
            self._editor_windows.pop(node_id)
        if node_id in self._editor_windows:
            win = self._editor_windows[node_id]
            win.raise_()
            win.activateWindow()
            return
        node = self._canvas._find_node(node_id)
        if node is None:
            return
        win = EditorWindow(node, parent=None)
        win.node_updated.connect(self._on_node_updated)
        win.dock_requested.connect(self._on_dock_requested)
        win.exec_requested.connect(self._exec_node)
        win.finished.connect(lambda _: self._editor_windows.pop(node_id, None))
        self._editor_windows[node_id] = win
        win.show()

    def _close_editor(self, node_id: str) -> None:
        if node_id in self._editor_windows:
            self._editor_windows.pop(node_id).close()

    def _close_all_editors(self) -> None:
        for win in list(self._editor_windows.values()):
            win.close()
        self._editor_windows.clear()

    def _on_node_updated(self, node_id: str, node: Node) -> None:
        self.mark_dirty()
        self._canvas.refresh_layout()
        self._canvas.select_node(node_id)
        self._update_status_node(node)

    # ── Selection ────────────────────────────────────────────────────────────

    def _on_node_selected(self, node_id: str) -> None:
        node = self._canvas._find_node(node_id)
        if node:
            self._update_status_node(node)

    # ── Dock handlers ────────────────────────────────────────────────────────

    def _on_dock_requested(self, node_id: str) -> None:
        win = self._editor_windows.get(node_id)
        if win is None:
            return
        node = self._canvas._find_node(node_id)
        if node is None:
            return
        form = win.extract_form()
        # Disconnect finished signal before closing to avoid pop-from-dict race.
        try:
            win.finished.disconnect()
        except RuntimeError:
            pass
        win.close()
        self._editor_windows.pop(node_id, None)
        self._dock_panel.dock(node_id, node, form)

    def _on_undock_requested(self, node_id: str) -> None:
        node = self._canvas._find_node(node_id)
        if node is None:
            return
        if node_id not in self._dock_panel._entries:
            return
        self._close_editor(node_id)
        form = self._dock_panel.undock(node_id)
        win = EditorWindow(node, form=form, parent=None)
        win.node_updated.connect(self._on_node_updated)
        win.dock_requested.connect(self._on_dock_requested)
        win.exec_requested.connect(self._exec_node)
        win.finished.connect(lambda _: self._editor_windows.pop(node_id, None))
        self._editor_windows[node_id] = win
        win.show()

    def _on_dock_close_requested(self, node_id: str) -> None:
        self._dock_panel.remove(node_id)

    def _on_name_changed(self, node_id: str, new_name: str) -> None:
        node = self._canvas._find_node(node_id)
        if node is None:
            return
        node.name = new_name
        self.mark_dirty()
        self._canvas.refresh_layout()
        win = self._editor_windows.get(node_id)
        if win:
            win.setWindowTitle(f"Éditer — {node.type} · {new_name}")

    def _on_notes_changed(self, text: str) -> None:
        if self._graph.notes == text:
            return
        self._graph.notes = text
        self.mark_dirty()

    def _sync_notes_from_graph(self) -> None:
        self._notes.set_text(self._graph.notes)

    def _sync_vars_from_graph(self) -> None:
        self._global_vars.set_variables(self._graph.variables)

    def _on_global_vars_changed(self) -> None:
        self._graph.variables = self._global_vars.get_variables()
        self.mark_dirty()

    def _apply_theme_colors(self, *_args) -> None:
        dark = is_dark(QApplication.instance())
        bg, text = _DESCRIPTION_COLORS[dark]
        self._notes.set_theme(bg, text)
        bg, text = _VARIABLES_COLORS[dark]
        self._global_vars.set_theme(bg, text)

    # ── Helpers ──────────────────────────────────────────────────────────────

    _MAX_RECENT = 20

    def _recent_paths(self) -> list[str]:
        settings = QSettings()
        value = settings.value("recentFiles", [])
        if isinstance(value, str):
            value = [value]
        return [str(v) for v in (value or []) if v]

    def _save_recent_paths(self, paths: list[str]) -> None:
        QSettings().setValue("recentFiles", paths)

    def _add_recent(self, path: Path) -> None:
        p = str(path.resolve())
        items = [x for x in self._recent_paths() if x != p]
        items.insert(0, p)
        self._save_recent_paths(items[: self._MAX_RECENT])
        self._refresh_recent_menu()

    def _remove_recent(self, path: Path) -> None:
        p = str(path.resolve())
        items = [x for x in self._recent_paths() if x != p]
        self._save_recent_paths(items)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        menu = self._recent_menu
        menu.clear()
        items = self._recent_paths()
        if not items:
            act = menu.addAction("(aucun)")
            act.setEnabled(False)
            return
        for p in items:
            path = Path(p)
            act = menu.addAction(f"{path.name}  —  {path.parent}")
            act.setToolTip(p)
            act.triggered.connect(lambda _checked=False, path=path: self._open_recent(path))
        menu.addSeparator()
        clear_act = menu.addAction("Vider la liste")
        clear_act.triggered.connect(self._clear_recent)

    def _open_recent(self, path: Path) -> None:
        if not self._confirm_discard():
            return
        self._open_path(path)

    def _clear_recent(self) -> None:
        self._save_recent_paths([])
        self._refresh_recent_menu()

    def _update_status_node(self, node: Node) -> None:
        active = "actif" if node.is_active else "inactif"
        self._status_node_label.setText(f"{node.type} · {node.name} · {active}")

    def mark_dirty(self) -> None:
        self._dirty = True
        self._update_title()

    def _update_title(self) -> None:
        name  = self._path.name if self._path else "Sans titre"
        dirty = " *" if self._dirty else ""
        self.setWindowTitle(f"Flower — {name}{dirty}")

    def closeEvent(self, event) -> None:
        if not self._confirm_discard():
            event.ignore()
            return
        self._close_all_editors()
        event.accept()
