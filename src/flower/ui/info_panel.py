from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QPushButton,
)
from PySide6.QtCore import Signal
from flower.models.node import Node


class InfoPanel(QWidget):
    edit_requested = Signal(str)  # node_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(180)

        self._lbl_type   = QLabel("—")
        self._lbl_name   = QLabel("—")
        self._lbl_active = QLabel("—")
        self._btn_edit   = QPushButton("Ouvrir l'éditeur")
        self._btn_edit.setEnabled(False)
        self._node_id: str | None = None

        form = QFormLayout()
        form.addRow("Type:", self._lbl_type)
        form.addRow("Nom:", self._lbl_name)
        form.addRow("Actif:", self._lbl_active)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Nœud sélectionné</b>"))
        layout.addLayout(form)
        layout.addStretch()
        layout.addWidget(self._btn_edit)

        self._btn_edit.clicked.connect(
            lambda: self.edit_requested.emit(self._node_id) if self._node_id else None
        )

    def show_node(self, node: Node) -> None:
        self._node_id = node.id
        self._lbl_type.setText(node.type.value)
        self._lbl_name.setText(node.name)
        self._lbl_active.setText("oui" if node.is_active else "non")
        self._btn_edit.setEnabled(True)

    def clear(self) -> None:
        self._node_id = None
        self._lbl_type.setText("—")
        self._lbl_name.setText("—")
        self._lbl_active.setText("—")
        self._btn_edit.setEnabled(False)
