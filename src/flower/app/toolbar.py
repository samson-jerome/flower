from __future__ import annotations
from PySide6.QtWidgets import QToolBar
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, Signal


class ToolBar(QToolBar):
    add_node_requested    = Signal()
    delete_node_requested = Signal()
    refresh_requested     = Signal()
    export_requested      = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOrientation(Qt.Orientation.Vertical)
        self.setMovable(False)

        act_add     = QAction("+", self)
        act_delete  = QAction("🗑", self)
        act_refresh = QAction("↺", self)
        act_export  = QAction("⬇", self)

        act_add.setToolTip("Ajouter un nœud enfant (C)")
        act_delete.setToolTip("Supprimer le nœud sélectionné (Del)")
        act_refresh.setToolTip("Recalculer le layout (R)")
        act_export.setToolTip("Exporter en XML")

        self.addAction(act_add)
        self.addAction(act_delete)
        self.addSeparator()
        self.addAction(act_refresh)
        self.addAction(act_export)

        act_add.triggered.connect(self.add_node_requested)
        act_delete.triggered.connect(self.delete_node_requested)
        act_refresh.triggered.connect(self.refresh_requested)
        act_export.triggered.connect(self.export_requested)
