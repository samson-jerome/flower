from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QSpinBox,
    QRadioButton, QButtonGroup, QStackedWidget, QApplication,
)
from qt_parameters import ComboParameter, ParameterForm, ParameterWidget
from flower.engine.models.node import NodeType
from flower.app.prefs import highlight_styles
from flower.app.editor.code_edit import CodeEdit
from flower.app.editor.highlighter import PygmentsHighlighter
from flower.app.editor.params import (
    CodeParameter, LiveStringParameter, setup_form, stretch_last_row,
)
from flower.i18n import t

SCRIPT_LANGUAGES: tuple[str, ...] = ("bash", "python", "sh", "powershell", "javascript")


def _follow_theme(highlighter: PygmentsHighlighter) -> None:
    """Keep `highlighter` in step with the colours in effect, the same way
    node_form.py, main_window.py and canvas.py do for their own. The type
    editors live as long as their NodeForm, so a change while the form is
    open has to be picked up -- they are not rebuilt.

    Two sources feed the same refresh: the palette (which background we
    render on) and the preference (which style was picked for it). Node
    editors are non-modal, so one can sit open behind the preferences
    dialog -- the second connection is what repaints it there and then."""
    app = QApplication.instance()
    if app is not None:
        app.paletteChanged.connect(lambda *_args: highlighter.refresh_theme())
    highlight_styles.notifier.changed.connect(highlighter.refresh_theme)


class NoopEditor(ParameterForm):
    def __init__(self, parent=None):
        super().__init__(name=NodeType.NOOP.value, parent=parent)
        setup_form(self, nested=True)

    def set_data(self, data: dict) -> None:
        pass

    def get_data(self) -> dict:
        return {}


def _labelled(param: ParameterWidget, label: str) -> ParameterWidget:
    """Every label is set explicitly: qt-parameters would otherwise show the
    parameter's technical name, untranslated."""
    param.set_label(label)
    return param


class ScriptEditor(ParameterForm):
    def __init__(self, parent=None):
        super().__init__(name=NodeType.SCRIPT.value, parent=parent)
        setup_form(self, nested=True)
        self._language = _labelled(ComboParameter("language"), t("form.script.language"))
        self._language.set_items(SCRIPT_LANGUAGES)
        self._body = _labelled(CodeParameter("body"), t("form.script.body"))

        self._highlighter = PygmentsHighlighter(
            self._body.edit.document(), self._language.value()
        )
        self._language.value_changed.connect(self._highlighter.set_language)
        _follow_theme(self._highlighter)

        self.add_parameter(self._language)
        self.add_parameter(self._body, alignment=Qt.AlignmentFlag.AlignTop)
        stretch_last_row(self)

    def set_data(self, data: dict) -> None:
        lang = data.get("language", "bash")
        # Mapped before set_value(): an unknown value would leave the combo
        # on no item at all and the parameter on None.
        if lang not in SCRIPT_LANGUAGES:
            lang = "bash"
        self._language.set_value(lang)
        # Set it explicitly: assigning the value that is already current emits
        # no signal, so the highlighter would keep the previous lexer.
        self._highlighter.set_language(lang)
        self._body.set_value(data.get("body", ""))

    def get_data(self) -> dict:
        return {"language": self._language.value(), "body": self._body.value()}


class DataEditor(ParameterForm):
    def __init__(self, parent=None):
        super().__init__(name=NodeType.DATA.value, parent=parent)
        setup_form(self, nested=True)
        self._command = _labelled(LiveStringParameter("command"), t("form.data.command"))
        self._content = _labelled(CodeParameter("content"), t("form.data.content"))

        # A DATA node declares no language, so the lexer is fixed -- python,
        # which reads well on the structured payloads these nodes carry.
        self._highlighter = PygmentsHighlighter(self._content.edit.document(), "python")
        _follow_theme(self._highlighter)

        self.add_parameter(self._command)
        self.add_parameter(self._content, alignment=Qt.AlignmentFlag.AlignTop)
        stretch_last_row(self)

    def set_data(self, data: dict) -> None:
        self._command.set_value(data.get("command", ""))
        self._content.set_value(data.get("content", ""))

    def get_data(self) -> dict:
        return {"command": self._command.value(), "content": self._content.value()}


class IfEditor(ParameterForm):
    def __init__(self, parent=None):
        super().__init__(name=NodeType.IF.value, parent=parent)
        setup_form(self, nested=True)
        self._condition = _labelled(LiveStringParameter("condition"), t("form.if.condition"))
        self.add_parameter(self._condition)

    def set_data(self, data: dict) -> None:
        self._condition.set_value(data.get("condition", ""))

    def get_data(self) -> dict:
        return {"condition": self._condition.value()}


class LoopEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._index           = QLineEdit()
        self._mode_range      = QRadioButton("Range")
        self._mode_list       = QRadioButton(t("form.loop.mode.list"))
        self._mode_expression = QRadioButton("Expression")
        self._mode_range.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._mode_range)
        self._mode_group.addButton(self._mode_list)
        self._mode_group.addButton(self._mode_expression)

        self._start = QSpinBox()
        self._start.setRange(-9999, 9999)
        self._end   = QSpinBox()
        self._end.setRange(-9999, 9999)
        self._step  = QSpinBox()
        self._step.setRange(1, 9999)
        self._step.setValue(1)
        self._items = QTextEdit()
        self._items.setPlaceholderText(t("form.loop.items.placeholder"))

        self._expression = CodeEdit()
        self._expression.setPlaceholderText(t("form.loop.expression.placeholder"))

        # The loop expression is always bash -- nothing to connect.
        self._highlighter = PygmentsHighlighter(self._expression.document(), "bash")
        _follow_theme(self._highlighter)

        self._stack = QStackedWidget()
        range_widget = QWidget()
        range_form = QFormLayout(range_widget)
        range_form.addRow("Start:", self._start)
        range_form.addRow("End:", self._end)
        range_form.addRow("Step:", self._step)
        self._stack.addWidget(range_widget)      # index 0 = range
        self._stack.addWidget(self._items)       # index 1 = list
        self._stack.addWidget(self._expression)  # index 2 = expression

        self._mode_range.toggled.connect(
            lambda checked: self._stack.setCurrentIndex(0) if checked else None
        )
        self._mode_list.toggled.connect(
            lambda checked: self._stack.setCurrentIndex(1) if checked else None
        )
        self._mode_expression.toggled.connect(
            lambda checked: self._stack.setCurrentIndex(2) if checked else None
        )

        mode_row = QFormLayout()
        mode_row.addRow(t("form.loop.mode"), self._mode_range)
        mode_row.addRow("", self._mode_list)
        mode_row.addRow("", self._mode_expression)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow(t("form.loop.index"), self._index)
        layout.addLayout(form)
        layout.addLayout(mode_row)
        layout.addWidget(self._stack)

    def set_data(self, data: dict) -> None:
        """Any mode value other than "list"/"expression" (including
        unrecognized legacy values) selects range, matching _loop_header()."""
        self._index.setText(data.get("index", ""))
        mode = data.get("mode", "range")
        if mode == "list":
            self._mode_list.setChecked(True)
        elif mode == "expression":
            self._mode_expression.setChecked(True)
        else:
            self._mode_range.setChecked(True)
        self._start.setValue(int(data.get("start", 0)))
        self._end.setValue(int(data.get("end", 0)))
        self._step.setValue(int(data.get("step", 1)))
        self._items.setPlainText(data.get("items", ""))
        self._expression.setPlainText(data.get("expression", ""))

    def get_data(self) -> dict:
        """Every key is returned whatever the active mode, so the inactive
        modes' values survive a round trip through the editor."""
        if self._mode_list.isChecked():
            mode = "list"
        elif self._mode_expression.isChecked():
            mode = "expression"
        else:
            mode = "range"
        return {
            "index":      self._index.text(),
            "mode":       mode,
            "start":      self._start.value(),
            "end":        self._end.value(),
            "step":       self._step.value(),
            "items":      self._items.toPlainText(),
            "expression": self._expression.toPlainText(),
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
