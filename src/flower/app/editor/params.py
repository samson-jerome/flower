"""What the node editors need on top of qt-parameters.

qt-parameters commits a text parameter's value on editingFinished, i.e. when
the field loses focus. The node form reads its values on Apply/Exec, which can
be triggered without the field ever losing focus (a button activated from
code, a shortcut), so the parameters here commit on every keystroke instead:
what the user sees in the field is always what get_data() returns.
"""
from __future__ import annotations
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QGridLayout, QPlainTextEdit, QSizePolicy
from qt_parameters import (
    IntParameter, ParameterEditor, ParameterForm, ParameterWidget, StringParameter,
)
from flower.app.editor.code_edit import CodeEdit

# Minimum width of the label column, shared by every grid so that the node
# form and the type editor nested in it line their fields up.
LABEL_WIDTH = 120


class LiveStringParameter(StringParameter):
    """A StringParameter whose value follows every keystroke."""

    def _init_text(self) -> None:
        # Re-run by set_area(), so the connection follows the new widget.
        super()._init_text()
        self.text.textChanged.connect(self._editing_finished)
        # qt-parameters fits an area to its lines only in set_value().
        if isinstance(self.text, QPlainTextEdit):
            self.text.textChanged.connect(self._refresh_height)


class BoundedIntParameter(IntParameter):
    """An IntParameter whose value follows every keystroke that leaves a
    complete, in-range number in the field.

    qt-parameters' own commit-on-edit turns incomplete text ("", "-", or "0"
    under a minimum of 1) into 0. The value keeps the last valid number
    instead, and leaving the field puts that number back in the text, as a
    QSpinBox does."""

    def _init_ui(self) -> None:
        super()._init_ui()
        self.line.textEdited.connect(self._commit_if_acceptable)
        self.line.installEventFilter(self)

    def _commit_if_acceptable(self, _text: str) -> None:
        if self.line.hasAcceptableInput():
            self.line.commit(update_text=False)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            watched is self.line
            and event.type() == QEvent.Type.FocusOut
            and not self.line.hasAcceptableInput()
        ):
            self.line.setText(str(self.value()))
        return False


class CodeParameter(ParameterWidget[str]):
    """A parameter holding a CodeEdit, for shell/python bodies."""

    _value: str = ""
    _default: str = ""

    def _init_ui(self) -> None:
        self.edit = CodeEdit()
        self.edit.textChanged.connect(
            lambda: super(CodeParameter, self).set_value(self.edit.toPlainText())
        )
        self._layout.addWidget(self.edit)
        self.setFocusProxy(self.edit)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    def set_value(self, value: str) -> None:
        super().set_value(value)
        blocked = self.edit.blockSignals(True)
        self.edit.setPlainText(value)
        self.edit.blockSignals(blocked)

    def set_placeholder(self, placeholder: str) -> None:
        self.edit.setPlaceholderText(placeholder)


def _grid(form: ParameterForm) -> QGridLayout:
    """The grid holding the parameters: a ParameterEditor moves it into its
    scroll area."""
    if isinstance(form, ParameterEditor):
        return form.scroll_area.widget().layout()
    return form.layout()


def setup_form(form: ParameterForm, nested: bool) -> ParameterForm:
    """Give `form` the label width and margins shared by the node editors.
    A nested form sits inside another one's grid, which already has margins."""
    grid = _grid(form)
    grid.setColumnMinimumWidth(1, LABEL_WIDTH)
    margin = 0 if nested else 4
    grid.setContentsMargins(margin, margin, margin, margin)
    return form


def stretch_last_row(form: ParameterForm) -> None:
    """Give the spare height to the last row holding a widget, instead of the
    empty row qt-parameters stretches below the content. Call it after the
    last add_*(): each of them resets the stretch."""
    grid = _grid(form)
    last = max(
        row + row_span - 1
        for row, _col, row_span, _col_span in (
            grid.getItemPosition(i) for i in range(grid.count())
        )
    )
    for row in range(grid.rowCount()):
        grid.setRowStretch(row, 1 if row == last else 0)
