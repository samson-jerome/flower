from __future__ import annotations
import uuid
from pathlib import Path
from datetime import datetime, timezone
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt
from flower.models.graph import Graph
from flower.models.node import Node, NodeType
from flower.ui.canvas import GraphCanvas
from flower.ui.toolbar import ToolBar
from flower.ui.info_panel import InfoPanel
from flower.ui.editor.editor_window import EditorWindow
from flower.io.xml_writer import write_flow
from flower.io.xml_reader import read_flow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flower")
        self.resize(1100, 700)

        self._graph:           Graph                     = Graph()
        self._path:            Path | None               = None
        self._dirty:           bool                      = False
        self._editor_windows:  dict[str, EditorWindow]   = {}

        self._toolbar = ToolBar(self)
        self._canvas  = GraphCanvas()
        self._info    = InfoPanel()

        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self._toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._canvas)
        splitter.addWidget(self._info)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self._build_menu()
        self._connect_signals()
        self._canvas.load_graph(self._graph)

    # ── Menu ────────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Fichier")
        file_menu.addAction("Nouveau",       self._new_file,  "Ctrl+N")
        file_menu.addAction("Ouvrir…",       self._open_file, "Ctrl+O")
        file_menu.addAction("Sauver",        self._save_file, "Ctrl+S")
        file_menu.addAction("Sauver sous…",  self._save_as,   "Ctrl+Shift+S")
        file_menu.addSeparator()
        file_menu.addAction("Quitter",       self.close,      "Ctrl+Q")

    def _connect_signals(self) -> None:
        self._canvas.node_selected.connect(self._on_node_selected)
        self._canvas.node_edit_requested.connect(self._open_editor)
        self._canvas.add_child_requested.connect(self._add_child_node)
        self._canvas.delete_requested.connect(self._delete_selected_node)
        self._canvas.node_active_changed.connect(self.mark_dirty)
        self._toolbar.add_node_requested.connect(self._add_child_node)
        self._toolbar.delete_node_requested.connect(self._delete_selected_node)
        self._toolbar.refresh_requested.connect(self._canvas.refresh_layout)
        self._toolbar.export_requested.connect(self._save_as)
        self._info.edit_requested.connect(self._open_editor)

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
        self._canvas.load_graph(self._graph)
        self._update_title()

    def _open_file(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir", "", "Flow files (*.flow)")
        if not path:
            return
        self._graph = read_flow(Path(path))
        self._path  = Path(path)
        self._dirty = False
        self._close_all_editors()
        self._canvas.load_graph(self._graph)
        self._update_title()

    def _save_file(self) -> None:
        if self._path is None:
            self._save_as()
            return
        self._graph.updated_at = datetime.now(timezone.utc).isoformat()
        write_flow(self._graph, self._path)
        self._dirty = False
        self._update_title()

    def _save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Sauver sous", "", "Flow files (*.flow)")
        if not path:
            return
        self._path = Path(path if path.endswith(".flow") else path + ".flow")
        self._save_file()

    # ── Node operations ─────────────────────────────────────────────────────

    def _add_child_node(self) -> None:
        new_node = Node(id=str(uuid.uuid4()), name="nouveau", type=NodeType.NOOP)
        parent_id = self._canvas._selected_id
        if parent_id:
            parent = self._canvas._find_node(parent_id)
            if parent:
                new_node.parent = parent
                parent.children.append(new_node)
            else:
                self._graph.roots.append(new_node)
        else:
            self._graph.roots.append(new_node)
        self.mark_dirty()
        self._canvas.refresh_layout()
        self._canvas.select_node(new_node.id)

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
        self.mark_dirty()
        self._canvas.refresh_layout()
        self._info.clear()

    # ── Editor windows ───────────────────────────────────────────────────────

    def _open_editor(self, node_id: str) -> None:
        # Remove stale entries: window accepted/closed but finished signal didn't clean up.
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
        self._info.show_node(node)

    # ── Selection ────────────────────────────────────────────────────────────

    def _on_node_selected(self, node_id: str) -> None:
        node = self._canvas._find_node(node_id)
        if node:
            self._info.show_node(node)

    # ── Helpers ──────────────────────────────────────────────────────────────

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
