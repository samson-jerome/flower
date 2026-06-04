from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QCheckBox, QHeaderView,
)
from flower.models.node import Variable


class VarsPanel(QWidget):
    """Tableau éditable de Variables (globales ou locales)."""

    COLUMNS = ("Nom", "Valeur", "Description", "Actif", "Op.")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._table = QTableWidget(0, len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(list(self.COLUMNS))
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        add_btn = QPushButton("+")
        add_btn.setFixedWidth(28)
        del_btn = QPushButton("−")
        del_btn.setFixedWidth(28)
        add_btn.clicked.connect(self._add_row)
        del_btn.clicked.connect(self._delete_selected)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(btn_layout)
        layout.addWidget(self._table)

    def _add_row(self):
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(""))
        self._table.setItem(row, 1, QTableWidgetItem(""))
        self._table.setItem(row, 2, QTableWidgetItem(""))
        chk = QCheckBox()
        chk.setChecked(True)
        self._table.setCellWidget(row, 3, chk)
        self._table.setItem(row, 4, QTableWidgetItem("="))

    def _delete_selected(self):
        for row in sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True):
            self._table.removeRow(row)

    def set_variables(self, variables: list[Variable]) -> None:
        self._table.setRowCount(0)
        for v in variables:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(v.name))
            self._table.setItem(row, 1, QTableWidgetItem(v.value))
            self._table.setItem(row, 2, QTableWidgetItem(v.description))
            chk = QCheckBox()
            chk.setChecked(v.active)
            self._table.setCellWidget(row, 3, chk)
            self._table.setItem(row, 4, QTableWidgetItem(v.operation))

    def get_variables(self) -> list[Variable]:
        result = []
        for row in range(self._table.rowCount()):
            chk = self._table.cellWidget(row, 3)
            result.append(Variable(
                name=self._table.item(row, 0).text() if self._table.item(row, 0) else "",
                value=self._table.item(row, 1).text() if self._table.item(row, 1) else "",
                description=self._table.item(row, 2).text() if self._table.item(row, 2) else "",
                active=chk.isChecked() if chk else True,
                operation=self._table.item(row, 4).text() if self._table.item(row, 4) else "=",
            ))
        return result
