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
        self._name_edit.editingFinished.connect(self._on_name_edited)

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
        # The header already shows an editable name; hide the form's name row.
        self._body.set_name_visible(False)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(separator)
        layout.addWidget(self._body)

    def _on_name_edited(self) -> None:
        # Keep the hidden form field in sync so a later save after undocking
        # does not overwrite the name with a stale value.
        self._body.set_name(self._name_edit.text())
        self.name_changed.emit(self._node_id, self._name_edit.text())

    def _toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        self._body.setVisible(not self._collapsed)
        self._toggle_btn.setText("▶" if self._collapsed else "▼")

    def extract_form(self) -> NodeForm:
        """Retire le NodeForm de ce DockEntry sans le détruire."""
        form = self._body
        form.set_name_visible(True)
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
        entry.show()

    def undock(self, node_id: str) -> NodeForm:
        entry = self._entries.pop(node_id)
        form = entry.extract_form()
        self._layout.removeWidget(entry)
        entry.deleteLater()
        return form

    def remove(self, node_id: str) -> None:
        entry = self._entries.pop(node_id, None)
        if entry is None:
            return
        self._layout.removeWidget(entry)
        entry.deleteLater()

    def clear(self) -> None:
        for node_id in list(self._entries):
            self.remove(node_id)
