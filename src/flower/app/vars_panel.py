from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QCheckBox, QComboBox, QHeaderView,
)
from flower.engine.models.node import Variable, VariableOperation
from flower.app.notes_panel import CollapsibleSection


class VarsPanel(CollapsibleSection):
    """Tableau éditable de Variables (globales ou locales), repliable."""

    COLUMNS = ("Nom", "Valeur", "Description", "Actif", "Op.")
    OPERATIONS = (
        (VariableOperation.ASSIGN, "Assignation"),
        (VariableOperation.CONCAT, "Concaténation"),
        (VariableOperation.ADD,    "Addition"),
    )

    variables_changed = Signal()

    def __init__(self, title: str = "Variables", parent=None):
        table = QTableWidget(0, len(self.COLUMNS))
        table.setHorizontalHeaderLabels(list(self.COLUMNS))
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        add_btn = QPushButton("+")
        add_btn.setFixedWidth(28)
        del_btn = QPushButton("−")
        del_btn.setFixedWidth(28)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(btn_layout)
        layout.addWidget(table)

        super().__init__(title, content, parent)
        self._table = table
        add_btn.clicked.connect(self._add_row)
        del_btn.clicked.connect(self._delete_selected)
        table.itemChanged.connect(lambda _item: self.variables_changed.emit())

    def _make_checkbox(self, checked: bool) -> QCheckBox:
        chk = QCheckBox()
        chk.setChecked(checked)
        chk.toggled.connect(lambda _checked: self.variables_changed.emit())
        return chk

    def _make_op_combo(self, operation: str) -> QComboBox:
        combo = QComboBox()
        for code, label in self.OPERATIONS:
            combo.addItem(label, code)
        idx = combo.findData(operation)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.currentIndexChanged.connect(lambda _idx: self.variables_changed.emit())
        return combo

    def _add_row(self):
        row = self._table.rowCount()
        self._table.insertRow(row)
        blocked = self._table.blockSignals(True)
        self._table.setItem(row, 0, QTableWidgetItem(""))
        self._table.setItem(row, 1, QTableWidgetItem(""))
        self._table.setItem(row, 2, QTableWidgetItem(""))
        self._table.blockSignals(blocked)
        self._table.setCellWidget(row, 3, self._make_checkbox(True))
        self._table.setCellWidget(row, 4, self._make_op_combo(VariableOperation.ASSIGN))
        self.variables_changed.emit()

    def _delete_selected(self):
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        for row in rows:
            self._table.removeRow(row)
        if rows:
            self.variables_changed.emit()

    def set_variables(self, variables: list[Variable]) -> None:
        blocked = self._table.blockSignals(True)
        self._table.setRowCount(0)
        for v in variables:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(v.name))
            self._table.setItem(row, 1, QTableWidgetItem(v.value))
            self._table.setItem(row, 2, QTableWidgetItem(v.description))
            self._table.setCellWidget(row, 3, self._make_checkbox(v.active))
            self._table.setCellWidget(row, 4, self._make_op_combo(v.operation))
        self._table.blockSignals(blocked)

    def get_variables(self) -> list[Variable]:
        result = []
        for row in range(self._table.rowCount()):
            chk = self._table.cellWidget(row, 3)
            combo = self._table.cellWidget(row, 4)
            result.append(Variable(
                name=self._table.item(row, 0).text() if self._table.item(row, 0) else "",
                value=self._table.item(row, 1).text() if self._table.item(row, 1) else "",
                description=self._table.item(row, 2).text() if self._table.item(row, 2) else "",
                active=chk.isChecked() if chk else True,
                operation=combo.currentData() if combo else VariableOperation.ASSIGN,
            ))
        return result
