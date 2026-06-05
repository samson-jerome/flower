# DockPanel & Status Bar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer l'InfoPanel (barre latérale droite) par un DockPanel accueillant des éditeurs de nœuds "dockés", et déplacer les infos du nœud sélectionné vers une status bar en bas de la fenêtre.

**Architecture:** Approche par reparentage de `NodeForm` : le widget de formulaire existant change de parent entre `EditorWindow` (flottant) et `DockEntry` (docké), sans duplication d'état. `QMainWindow.statusBar()` est utilisé nativement avec un `QLabel` permanent pour le nœud sélectionné et `showMessage()` pour les messages passagers.

**Tech Stack:** Python 3.11+, PySide6, pytest avec fixture `qapp` (mode offscreen via `QT_QPA_PLATFORM=offscreen`).

---

## Carte des fichiers

| Fichier | Action | Responsabilité |
|---|---|---|
| `src/flower/ui/dock_panel.py` | Créer | `DockEntry` (widget d'une entrée dockée) + `DockPanel` (conteneur scrollable) |
| `src/flower/ui/info_panel.py` | Supprimer | Remplacé par `dock_panel.py` |
| `src/flower/ui/editor/editor_window.py` | Modifier | Ajout signal `dock_requested`, bouton "Dock", méthode `extract_form()`, paramètre `form=` optionnel |
| `src/flower/ui/main_window.py` | Modifier | Status bar, DockPanel à la place d'InfoPanel, nouveaux handlers de signaux |
| `tests/test_ui_dock_panel.py` | Créer | Tests unitaires de `DockEntry` et `DockPanel` |
| `tests/test_ui_editor_window.py` | Modifier | Tests pour `dock_requested`, `extract_form()`, constructeur avec `form=` |

---

## Task 1 : Créer `dock_panel.py` — `DockEntry` + `DockPanel`

**Files:**
- Create: `src/flower/ui/dock_panel.py`
- Create: `tests/test_ui_dock_panel.py`

### Étape 1.1 — Écrire les tests (échec attendu)

- [ ] Créer `tests/test_ui_dock_panel.py` :

```python
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
    node = _node()
    panel.dock(node.id, node, _form(node))
    entry = panel._entries[node.id]
    assert entry._body.isVisible()
    entry._toggle_btn.click()
    assert not entry._body.isVisible()
    entry._toggle_btn.click()
    assert entry._body.isVisible()
```

- [ ] Lancer les tests pour vérifier l'échec :

```bash
cd /home/jsamson/workspace/dev/perso/python/flower
python -m pytest tests/test_ui_dock_panel.py -v 2>&1 | head -30
```

Résultat attendu : `ImportError: cannot import name 'DockPanel' from 'flower.ui.dock_panel'`

### Étape 1.2 — Implémenter `dock_panel.py`

- [ ] Créer `src/flower/ui/dock_panel.py` :

```python
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QScrollArea, QFrame,
)
from PySide6.QtCore import Signal
from flower.models.node import Node
from flower.ui.editor.node_form import NodeForm


class DockEntry(QWidget):
    """Un éditeur de nœud docké dans le DockPanel."""

    undock_requested = Signal(str)   # node_id
    close_requested  = Signal(str)   # node_id
    name_changed     = Signal(str, str)  # node_id, new_name

    def __init__(self, node_id: str, node_name: str, form: NodeForm, parent=None):
        super().__init__(parent)
        self._node_id = node_id
        self._collapsed = False

        self._toggle_btn = QPushButton("▼")
        self._toggle_btn.setFixedWidth(24)
        self._toggle_btn.clicked.connect(self._toggle_collapse)

        self._name_edit = QLineEdit(node_name)
        self._name_edit.editingFinished.connect(
            lambda: self.name_changed.emit(self._node_id, self._name_edit.text())
        )

        self._undock_btn = QPushButton("↗")
        self._undock_btn.setFixedWidth(24)
        self._undock_btn.setToolTip("Ouvrir en fenêtre flottante")
        self._undock_btn.clicked.connect(
            lambda: self.undock_requested.emit(self._node_id)
        )

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedWidth(24)
        self._close_btn.clicked.connect(
            lambda: self.close_requested.emit(self._node_id)
        )

        header = QHBoxLayout()
        header.setContentsMargins(4, 2, 4, 2)
        header.addWidget(self._toggle_btn)
        header.addWidget(self._name_edit)
        header.addWidget(self._undock_btn)
        header.addWidget(self._close_btn)

        self._body = form
        self._body.setParent(self)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(separator)
        layout.addWidget(self._body)

    def _toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        self._body.setVisible(not self._collapsed)
        self._toggle_btn.setText("▶" if self._collapsed else "▼")

    def extract_form(self) -> NodeForm:
        """Retire le NodeForm de ce DockEntry sans le détruire."""
        form = self._body
        form.setParent(None)
        return form


class DockPanel(QWidget):
    """Barre latérale droite accueillant des éditeurs de nœuds dockés."""

    undock_requested = Signal(str)       # node_id
    close_requested  = Signal(str)       # node_id
    name_changed     = Signal(str, str)  # node_id, new_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(220)
        self._entries: dict[str, DockEntry] = {}

        self._inner = QWidget()
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self._inner)
        scroll.setWidgetResizable(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Public API ───────────────────────────────────────────────────────────

    def dock(self, node_id: str, node: Node, form: NodeForm) -> None:
        if node_id in self._entries:
            return
        entry = DockEntry(node_id, node.name, form, parent=self._inner)
        entry.undock_requested.connect(self.undock_requested)
        entry.close_requested.connect(self.close_requested)
        entry.name_changed.connect(self.name_changed)
        self._entries[node_id] = entry
        # Insert before the trailing stretch (last item).
        self._layout.insertWidget(self._layout.count() - 1, entry)

    def undock(self, node_id: str) -> NodeForm:
        entry = self._entries.pop(node_id)
        form = entry.extract_form()
        self._layout.removeWidget(entry)
        entry.deleteLater()
        return form

    def remove(self, node_id: str) -> None:
        entry = self._entries.pop(node_id)
        self._layout.removeWidget(entry)
        entry.deleteLater()

    def clear(self) -> None:
        for node_id in list(self._entries):
            self.remove(node_id)
```

### Étape 1.3 — Lancer les tests et vérifier le succès

- [ ] Lancer les tests :

```bash
cd /home/jsamson/workspace/dev/perso/python/flower
python -m pytest tests/test_ui_dock_panel.py -v
```

Résultat attendu : tous les tests passent (`PASSED`).

### Étape 1.4 — Supprimer `info_panel.py`

- [ ] Supprimer le fichier devenu obsolète :

```bash
git rm src/flower/ui/info_panel.py
```

### Étape 1.5 — Committer

- [ ] Committer :

```bash
git add src/flower/ui/dock_panel.py tests/test_ui_dock_panel.py
git commit -m "feat: add DockPanel and DockEntry, remove InfoPanel"
```

---

## Task 2 : Modifier `editor_window.py` — bouton Dock + `extract_form()`

**Files:**
- Modify: `src/flower/ui/editor/editor_window.py`
- Modify: `tests/test_ui_editor_window.py`

### Étape 2.1 — Écrire les nouveaux tests (échec attendu)

- [ ] Ajouter à la fin de `tests/test_ui_editor_window.py` :

```python
from flower.ui.editor.node_form import NodeForm


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
```

- [ ] Lancer pour vérifier l'échec :

```bash
python -m pytest tests/test_ui_editor_window.py -v 2>&1 | tail -20
```

Résultat attendu : `AttributeError: 'EditorWindow' object has no attribute 'extract_form'` (ou similaire).

### Étape 2.2 — Modifier `editor_window.py`

- [ ] Remplacer le contenu de `src/flower/ui/editor/editor_window.py` :

```python
from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea,
)
from PySide6.QtCore import Signal
from flower.models.node import Node
from flower.ui.editor.node_form import NodeForm


class EditorWindow(QDialog):
    """Non-modal edit dialog for a node — one instance per node_id."""

    node_updated  = Signal(str, object)  # (node_id, Node)
    dock_requested = Signal(str)          # node_id

    def __init__(self, node: Node, form: NodeForm | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Éditer — {node.type} · {node.name}")
        self.setMinimumSize(480, 520)
        self._node = node
        self._form = form if form is not None else NodeForm(node)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._form)
        self._scroll.setWidgetResizable(True)

        cancel_btn   = QPushButton("Annuler")
        apply_btn    = QPushButton("Appliquer")
        save_btn     = QPushButton("Sauver && Fermer")
        self._dock_btn = QPushButton("Dock")

        cancel_btn.clicked.connect(self.reject)
        apply_btn.clicked.connect(self._apply)
        save_btn.clicked.connect(self._save_and_close)
        self._dock_btn.clicked.connect(
            lambda: self.dock_requested.emit(self._node.id)
        )

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._dock_btn)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(save_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self._scroll)
        layout.addLayout(btn_row)

    def _apply(self) -> None:
        self._form.apply_to_node()
        self.setWindowTitle(f"Éditer — {self._node.type} · {self._node.name}")
        self.node_updated.emit(self._node.id, self._node)

    def _save_and_close(self) -> None:
        self._apply()
        self.accept()

    def extract_form(self) -> NodeForm:
        """Remove the NodeForm from this window without destroying it."""
        self._form.setParent(None)
        return self._form

    def node_id(self) -> str:
        return self._node.id
```

### Étape 2.3 — Lancer tous les tests EditorWindow

- [ ] Lancer :

```bash
python -m pytest tests/test_ui_editor_window.py -v
```

Résultat attendu : tous les tests passent.

### Étape 2.4 — Committer

- [ ] Committer :

```bash
git add src/flower/ui/editor/editor_window.py tests/test_ui_editor_window.py
git commit -m "feat: add Dock button, dock_requested signal and extract_form() to EditorWindow"
```

---

## Task 3 : Modifier `main_window.py` — status bar + DockPanel + handlers

**Files:**
- Modify: `src/flower/ui/main_window.py`

*Note : MainWindow est un orchestrateur pur (wiring de signaux, pas de logique métier isolable). On vérifie par test manuel en lançant l'application.*

### Étape 3.1 — Remplacer `main_window.py`

- [ ] Remplacer le contenu de `src/flower/ui/main_window.py` :

```python
from __future__ import annotations
import uuid
from pathlib import Path
from datetime import datetime, timezone
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QMessageBox, QFileDialog, QLabel,
)
from PySide6.QtCore import Qt
from flower.models.graph import Graph
from flower.models.node import Node, NodeType
from flower.ui.canvas import GraphCanvas
from flower.ui.toolbar import ToolBar
from flower.ui.dock_panel import DockPanel
from flower.ui.editor.editor_window import EditorWindow
from flower.io.xml_writer import write_flow
from flower.io.xml_reader import read_flow


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

        self._toolbar    = ToolBar(self)
        self._canvas     = GraphCanvas()
        self._dock_panel = DockPanel()

        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self._toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._canvas)
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
        self._status_node_label.clear()
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
        self._dock_panel.clear()
        self._canvas.load_graph(self._graph)
        self._status_node_label.clear()
        self._update_title()

    def _save_file(self) -> None:
        if self._path is None:
            self._save_as()
            return
        self._graph.updated_at = datetime.now(timezone.utc).isoformat()
        write_flow(self._graph, self._path)
        self._dirty = False
        self._update_title()
        self.statusBar().showMessage("Fichier sauvegardé", 3000)

    def _save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Sauver sous", "", "Flow files (*.flow)")
        if not path:
            return
        self._path = Path(path if path.endswith(".flow") else path + ".flow")
        self._save_file()

    # ── Node operations ─────────────────────────────────────────────────────

    def _add_child_node(self) -> None:
        new_node = Node(id=str(uuid.uuid4()), name=_unique_name("nouveau", self._graph), type=NodeType.NOOP)
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
        self._dock_panel.remove(node_id) if node_id in self._dock_panel._entries else None
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
        win.finished.disconnect()
        win.close()
        self._editor_windows.pop(node_id, None)
        self._dock_panel.dock(node_id, node, form)

    def _on_undock_requested(self, node_id: str) -> None:
        node = self._canvas._find_node(node_id)
        if node is None:
            return
        form = self._dock_panel.undock(node_id)
        win = EditorWindow(node, form=form, parent=None)
        win.node_updated.connect(self._on_node_updated)
        win.dock_requested.connect(self._on_dock_requested)
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

    # ── Helpers ──────────────────────────────────────────────────────────────

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
```

### Étape 3.2 — Lancer la suite de tests complète

- [ ] Lancer tous les tests pour détecter les régressions :

```bash
python -m pytest tests/ -v
```

Résultat attendu : tous les tests passent. Si un test échoue sur l'import de `InfoPanel` depuis un autre fichier, corriger l'import dans ce fichier.

### Étape 3.3 — Test manuel : vérifier l'application

- [ ] Lancer l'application :

```bash
python -m flower
```

Vérifier :
1. La fenêtre s'ouvre avec le canvas à gauche et le DockPanel (vide) à droite.
2. La status bar en bas est visible.
3. Sélectionner un nœud → la status bar affiche `type · nom · actif/inactif`.
4. Double-cliquer sur un nœud → `EditorWindow` s'ouvre avec le bouton "Dock".
5. Cliquer "Dock" → la fenêtre flottante se ferme, un `DockEntry` apparaît dans le panel droit avec le nom du nœud, les boutons ▼, ↗, ✕.
6. Cliquer ▼ → le formulaire se réduit. Re-cliquer → il se rouvre.
7. Modifier le nom dans le `DockEntry` + Tab → le canvas se met à jour.
8. Cliquer ↗ → le `DockEntry` disparaît, une `EditorWindow` flottante s'ouvre.
9. Cliquer ✕ → le `DockEntry` disparaît.
10. Sauvegarder (Ctrl+S) → "Fichier sauvegardé" apparaît 3 s dans la status bar.
11. Supprimer un nœud → "Nœud supprimé" apparaît 3 s dans la status bar.
12. Nouveau fichier (Ctrl+N) → les DockEntries sont effacés.

### Étape 3.4 — Committer

- [ ] Committer :

```bash
git add src/flower/ui/main_window.py
git commit -m "feat: replace InfoPanel with DockPanel, add status bar node info"
```

---

## Self-Review

**Couverture spec :**
- ✅ Status bar QLabel permanent (§1 zone permanente) → Task 3 `_update_status_node()`
- ✅ showMessage passager (§1 messages passagers) → Task 3 `_save_file`, `_delete_selected_node`
- ✅ DockPanel + DockEntry (§2) → Task 1
- ✅ Signaux undock_requested / close_requested / name_changed → Task 1
- ✅ API dock / undock / remove / clear → Task 1
- ✅ Toggle collapse → Task 1 test + implémentation
- ✅ EditorWindow dock_requested + extract_form() (§3) → Task 2
- ✅ Séquence Dock (§3) → Task 3 `_on_dock_requested`
- ✅ Séquence Undock (§3) → Task 3 `_on_undock_requested`
- ✅ EditorWindow avec form= existant → Task 2
- ✅ Suppressions InfoPanel (§4) → Task 1 (git rm) + Task 3 (import supprimé)
- ✅ `_on_name_changed` met à jour node.name + mark_dirty + refresh_layout → Task 3
- ✅ clear() sur _new_file / _open_file → Task 3
