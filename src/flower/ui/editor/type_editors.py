from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel,
    QLineEdit, QTextEdit, QComboBox, QSpinBox,
    QRadioButton, QButtonGroup, QStackedWidget,
)
from PySide6.QtGui import QFont
from flower.models.node import NodeType


class NoopEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        QVBoxLayout(self)

    def set_data(self, data: dict) -> None:
        pass

    def get_data(self) -> dict:
        return {}


class ScriptEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._language = QComboBox()
        self._language.addItems(["bash", "python", "sh", "powershell", "javascript"])

        self._body = QTextEdit()
        mono = QFont("Monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self._body.setFont(mono)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Langage:", self._language)
        layout.addLayout(form)
        layout.addWidget(QLabel("Corps:"))
        layout.addWidget(self._body)

    def set_data(self, data: dict) -> None:
        lang = data.get("language", "bash")
        idx = self._language.findText(lang)
        self._language.setCurrentIndex(idx if idx >= 0 else 0)
        self._body.setPlainText(data.get("body", ""))

    def get_data(self) -> dict:
        return {"language": self._language.currentText(), "body": self._body.toPlainText()}


class DataEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._command = QLineEdit()
        self._content = QTextEdit()
        mono = QFont("Monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self._content.setFont(mono)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Commande:", self._command)
        layout.addLayout(form)
        layout.addWidget(QLabel("Contenu:"))
        layout.addWidget(self._content)

    def set_data(self, data: dict) -> None:
        self._command.setText(data.get("command", ""))
        self._content.setPlainText(data.get("content", ""))

    def get_data(self) -> dict:
        return {"command": self._command.text(), "content": self._content.toPlainText()}


class IfEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._condition = QLineEdit()
        QFormLayout(self).addRow("Condition:", self._condition)

    def set_data(self, data: dict) -> None:
        self._condition.setText(data.get("condition", ""))

    def get_data(self) -> dict:
        return {"condition": self._condition.text()}


class LoopEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._index      = QLineEdit()
        self._mode_range = QRadioButton("Range")
        self._mode_list  = QRadioButton("Liste")
        self._mode_range.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._mode_range)
        self._mode_group.addButton(self._mode_list)

        self._start = QSpinBox()
        self._start.setRange(-9999, 9999)
        self._end   = QSpinBox()
        self._end.setRange(-9999, 9999)
        self._step  = QSpinBox()
        self._step.setRange(1, 9999)
        self._step.setValue(1)
        self._items = QTextEdit()
        self._items.setPlaceholderText("Un item par ligne")

        self._stack = QStackedWidget()
        range_widget = QWidget()
        range_form = QFormLayout(range_widget)
        range_form.addRow("Start:", self._start)
        range_form.addRow("End:", self._end)
        range_form.addRow("Step:", self._step)
        self._stack.addWidget(range_widget)  # index 0 = range
        self._stack.addWidget(self._items)   # index 1 = list

        self._mode_range.toggled.connect(
            lambda checked: self._stack.setCurrentIndex(0) if checked else None
        )
        self._mode_list.toggled.connect(
            lambda checked: self._stack.setCurrentIndex(1) if checked else None
        )

        mode_row = QFormLayout()
        mode_row.addRow("Mode:", self._mode_range)
        mode_row.addRow("", self._mode_list)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Index:", self._index)
        layout.addLayout(form)
        layout.addLayout(mode_row)
        layout.addWidget(self._stack)

    def set_data(self, data: dict) -> None:
        self._index.setText(data.get("index", ""))
        if data.get("mode", "range") == "list":
            self._mode_list.setChecked(True)
        else:
            self._mode_range.setChecked(True)
        self._start.setValue(int(data.get("start", 0)))
        self._end.setValue(int(data.get("end", 0)))
        self._step.setValue(int(data.get("step", 1)))
        self._items.setPlainText(data.get("items", ""))

    def get_data(self) -> dict:
        return {
            "index": self._index.text(),
            "mode":  "list" if self._mode_list.isChecked() else "range",
            "start": self._start.value(),
            "end":   self._end.value(),
            "step":  self._step.value(),
            "items": self._items.toPlainText(),
        }


_EDITORS: dict[NodeType, type] = {
    NodeType.NOOP:   NoopEditor,
    NodeType.SCRIPT: ScriptEditor,
    NodeType.DATA:   DataEditor,
    NodeType.IF:     IfEditor,
    NodeType.LOOP:   LoopEditor,
}


def make_type_editor(node_type: NodeType, parent=None) -> QWidget:
    return _EDITORS.get(node_type, NoopEditor)(parent)
