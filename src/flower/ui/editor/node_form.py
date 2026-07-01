from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout,
    QLineEdit, QCheckBox, QComboBox, QStackedWidget, QSplitter, QScrollArea,
)
from PySide6.QtCore import Qt
from flower.models.node import Node, NodeType
from flower.ui.editor.type_editors import make_type_editor
from flower.ui.vars_panel import VarsPanel
from flower.ui.notes_panel import NotesPanel, bind_notes_to_splitter

DESCRIPTION_BG = "#898989"   # gris souris
DESCRIPTION_TEXT = "#F0F0F0"   # gris souris
VARIABLES_BG   = "#2e5f66"   # bleu pétrole
VARIABLES_TEXT = "#f0f0f0"


class NodeForm(QWidget):
    """Formulaire d'édition complet pour un nœud.

    Trois sections dans un splitter vertical :
    description, variables (toutes deux indépendantes du type de nœud),
    puis le corps du nœud (type, nom, actif et l'éditeur spécifique au type).
    """

    def __init__(self, node: Node, parent=None):
        super().__init__(parent)
        self._node = node

        # ── Section 1 : description ──────────────────────────────────────────
        self._description = NotesPanel(title="Description")
        self._description.set_text(node.description)
        self._description.set_theme(DESCRIPTION_BG, DESCRIPTION_TEXT)

        # ── Section 2 : variables ────────────────────────────────────────────
        self._vars = VarsPanel(title="Variables")
        self._vars.set_variables(node.variables)
        self._vars.set_theme(VARIABLES_BG, VARIABLES_TEXT)

        # ── Section 3 : corps du nœud ────────────────────────────────────────
        self._type_combo = QComboBox()
        for nt in NodeType:
            self._type_combo.addItem(nt.value, nt)
        self._type_combo.setCurrentText(node.type.value)

        self._name   = QLineEdit(node.name)
        self._active = QCheckBox()
        self._active.setChecked(node.is_active)

        self._stack: QStackedWidget = QStackedWidget()
        self._type_editors: dict[NodeType, QWidget] = {}
        for nt in NodeType:
            editor = make_type_editor(nt)
            self._type_editors[nt] = editor
            self._stack.addWidget(editor)

        self._refresh_type_editor(node.type)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)

        self._form_layout = QFormLayout()
        form = self._form_layout
        form.addRow("Type:", self._type_combo)
        form.addRow("Nom:", self._name)
        form.addRow("Actif:", self._active)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(4, 4, 4, 4)
        body_layout.addLayout(form)
        body_layout.addWidget(self._stack)

        body_scroll = QScrollArea()
        body_scroll.setWidget(body)
        body_scroll.setWidgetResizable(True)

        # ── Assemblage ───────────────────────────────────────────────────────
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.addWidget(self._description)
        self._splitter.addWidget(self._vars)
        self._splitter.addWidget(body_scroll)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setStretchFactor(2, 1)
        self._splitter.setSizes([100, 180, 320])
        bind_notes_to_splitter(self._description, self._splitter, index=0)
        bind_notes_to_splitter(self._vars, self._splitter, index=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._splitter)

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
            "description": self._description.text(),
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
