"""What the node editors need on top of qt-parameters.

qt-parameters commits a text parameter's value on editingFinished, i.e. when
the field loses focus. The node form reads its values on Apply/Exec, which can
be triggered without the field ever losing focus (a button activated from
code, a shortcut), so the parameters here commit on every keystroke instead:
what the user sees in the field is always what get_data() returns.
"""
from __future__ import annotations
from PySide6.QtWidgets import QGridLayout, QSizePolicy
from qt_parameters import ParameterEditor, ParameterForm, ParameterWidget, StringParameter
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
