from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout,
    QLineEdit, QCheckBox, QComboBox, QStackedWidget, QSplitter, QScrollArea,
    QApplication, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from flower.models.node import Node, NodeType, MAX_CHILDREN, EXECUTABLE_TYPES
from flower.ui.editor.type_editors import make_type_editor
from flower.ui.vars_panel import VarsPanel
from flower.ui.notes_panel import NotesPanel, bind_notes_to_splitter
from flower.ui.theme import is_dark

# (background, text) pairs, keyed by whether the app is currently dark.
_DESCRIPTION_COLORS = {
    True:  ("#898989", "#F0F0F0"),   # gris souris
    False: ("#D8D8D8", "#2B2B2B"),   # gris souris clair
}
_VARIABLES_COLORS = {
    True:  ("#2E5F66", "#F0F0F0"),   # bleu pétrole
    False: ("#CFE6E9", "#1B3A40"),   # bleu pétrole clair
}


class NodeForm(QWidget):
    """Formulaire d'édition complet pour un nœud.

    Trois sections dans un splitter vertical :
    description, variables (toutes deux indépendantes du type de nœud),
    puis le corps du nœud (type, nom, actif et l'éditeur spécifique au type).
    """

    exec_state_changed = Signal(bool)

    def __init__(self, node: Node, parent=None):
        super().__init__(parent)
        self._node = node

        # ── Section 1 : description ──────────────────────────────────────────
        self._description = NotesPanel(title="Description")
        self._description.set_text(node.description)

        # ── Section 2 : variables ────────────────────────────────────────────
        self._vars = VarsPanel(title="Variables")
        self._vars.set_variables(node.variables)

        self._apply_theme_colors()
        app = QApplication.instance()
        if app is not None:
            app.paletteChanged.connect(self._apply_theme_colors)

        # ── Section 3 : corps du nœud ────────────────────────────────────────
        self._type_combo = QComboBox()
        for nt in NodeType:
            self._type_combo.addItem(nt.value, nt)
        self._type_combo.setCurrentText(node.type.value)

        self._name   = QLineEdit(node.name)
        self._active = QCheckBox()
        self._active.setChecked(node.is_active)
        self._executable = QCheckBox()
        self._executable.setChecked(node.is_executable)

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
        form.addRow("Exécutable:", self._executable)
        self._refresh_executable_row(node.type)
        self._executable.toggled.connect(self._emit_exec_state)
        self._active.toggled.connect(self._emit_exec_state)

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

    def _apply_theme_colors(self, *_args) -> None:
        dark = is_dark(QApplication.instance())
        bg, text = _DESCRIPTION_COLORS[dark]
        self._description.set_theme(bg, text)
        bg, text = _VARIABLES_COLORS[dark]
        self._vars.set_theme(bg, text)

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
        ntype = NodeType(self._type_combo.currentData())
        max_children = MAX_CHILDREN.get(ntype)
        if max_children is not None and len(self._node.children) > max_children:
            QMessageBox.warning(
                self, "Type incompatible",
                f"Un nœud « {ntype.value} » ne peut avoir plus de {max_children} enfant(s) "
                f"(celui-ci en a {len(self._node.children)}). "
                "Réduisez d'abord le nombre d'enfants avant de changer le type.",
            )
            blocked = self._type_combo.blockSignals(True)
            self._type_combo.setCurrentText(self._node.type.value)
            self._type_combo.blockSignals(blocked)
            # The combo is back on the node's own type, so the executable row
            # has to follow it: otherwise it stays disabled from the type that
            # was just refused, with an eligible type showing in the combo.
            self._refresh_executable_row(self._node.type)
            self._emit_exec_state()
            return
        self._refresh_type_editor(ntype)
        self._refresh_executable_row(ntype)
        self._emit_exec_state()

    def _refresh_type_editor(self, ntype: NodeType) -> None:
        editor = self._type_editors[ntype]
        if ntype == self._node.type:
            editor.set_data(self._node.type_data)
        self._stack.setCurrentWidget(editor)

    def exec_state(self) -> bool:
        """Whether the Exec affordance should be live for the values currently
        in the form -- not for those in the node, which only receives them on
        apply."""
        return (
            self._executable.isChecked()
            and NodeType(self._type_combo.currentData()) in EXECUTABLE_TYPES
            and self._active.isChecked()
        )

    def _emit_exec_state(self, *_args) -> None:
        self.exec_state_changed.emit(self.exec_state())

    def _refresh_executable_row(self, ntype: NodeType) -> None:
        """Only script and data nodes can be run up to, so for any other type
        the row is cleared and disabled and the flag cannot be set."""
        eligible = ntype in EXECUTABLE_TYPES
        if not eligible:
            self._executable.setChecked(False)
        self._executable.setEnabled(eligible)
        label = self._form_layout.labelForField(self._executable)
        if label:
            label.setEnabled(eligible)

    def get_node_data(self) -> dict:
        ntype = NodeType(self._type_combo.currentData())
        return {
            "name":          self._name.text(),
            "type":          ntype,
            "is_active":     self._active.isChecked(),
            "is_executable": self._executable.isChecked() and ntype in EXECUTABLE_TYPES,
            "description":   self._description.text(),
            "type_data":     self._type_editors[ntype].get_data(),
            "variables":     self._vars.get_variables(),
        }

    def apply_to_node(self) -> Node:
        data = self.get_node_data()
        self._node.name          = data["name"]
        self._node.type          = data["type"]
        self._node.is_active     = data["is_active"]
        self._node.is_executable = data["is_executable"]
        self._node.description   = data["description"]
        self._node.type_data     = data["type_data"]
        self._node.variables     = data["variables"]
        return self._node
