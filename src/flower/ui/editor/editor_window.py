from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea,
)
from PySide6.QtCore import Signal
from flower.models.node import Node
from flower.ui.editor.node_form import NodeForm


class EditorWindow(QDialog):
    """Non-modal edit dialog for a node — one instance per node_id."""

    node_updated   = Signal(str, object)  # (node_id, Node)
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

        cancel_btn     = QPushButton("Annuler")
        apply_btn      = QPushButton("Appliquer")
        save_btn       = QPushButton("Sauver && Fermer")
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
