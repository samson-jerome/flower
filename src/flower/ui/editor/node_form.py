from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel,
    QLineEdit, QTextEdit, QCheckBox, QComboBox, QStackedWidget,
)
from flower.models.node import Node, NodeType
from flower.ui.editor.type_editors import make_type_editor
from flower.ui.vars_panel import VarsPanel


class NodeForm(QWidget):
    """Formulaire d'édition complet pour un nœud."""

    def __init__(self, node: Node, parent=None):
        super().__init__(parent)
        self._node = node

        self._type_combo = QComboBox()
        for nt in NodeType:
            self._type_combo.addItem(nt.value, nt)
        self._type_combo.setCurrentText(node.type.value)

        self._name   = QLineEdit(node.name)
        self._active = QCheckBox()
        self._active.setChecked(node.is_active)
        self._desc   = QTextEdit(node.description)
        self._desc.setFixedHeight(60)

        self._stack: QStackedWidget = QStackedWidget()
        self._type_editors: dict[NodeType, QWidget] = {}
        for nt in NodeType:
            editor = make_type_editor(nt)
            self._type_editors[nt] = editor
            self._stack.addWidget(editor)

        self._refresh_type_editor(node.type)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)

        self._vars = VarsPanel()
        self._vars.set_variables(node.variables)

        self._form_layout = QFormLayout()
        form = self._form_layout
        form.addRow("Type:", self._type_combo)
        form.addRow("Nom:", self._name)
        form.addRow("Actif:", self._active)
        form.addRow("Description:", self._desc)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._stack)
        layout.addWidget(QLabel("Variables locales:"))
        layout.addWidget(self._vars)

    def set_name_visible(self, visible: bool) -> None:
        """Hide the name row when the form is docked (the dock header already
        shows an editable name)."""
        label = self._form_layout.labelForField(self._name)
        if label:
            label.setVisible(visible)
        self._name.setVisible(visible)

    def set_name(self, name: str) -> None:
        self._name.setText(name)

    def _on_type_changed(self, _index: int) -> None:
        self._refresh_type_editor(NodeType(self._type_combo.currentData()))

    def _refresh_type_editor(self, ntype: NodeType) -> None:
        editor = self._type_editors[ntype]
        if ntype == self._node.type:
            editor.set_data(self._node.type_data)
        self._stack.setCurrentWidget(editor)

    def get_node_data(self) -> dict:
        ntype = NodeType(self._type_combo.currentData())
        return {
            "name":        self._name.text(),
            "type":        ntype,
            "is_active":   self._active.isChecked(),
            "description": self._desc.toPlainText(),
            "type_data":   self._type_editors[ntype].get_data(),
            "variables":   self._vars.get_variables(),
        }

    def apply_to_node(self) -> Node:
        data = self.get_node_data()
        self._node.name        = data["name"]
        self._node.type        = data["type"]
        self._node.is_active   = data["is_active"]
        self._node.description = data["description"]
        self._node.type_data   = data["type_data"]
        self._node.variables   = data["variables"]
        return self._node
