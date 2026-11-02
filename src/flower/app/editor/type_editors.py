from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QStackedWidget, QApplication
from qt_parameters import ComboParameter, IntParameter, ParameterForm, ParameterWidget
from flower.engine.models.node import NodeType
from flower.app.prefs import highlight_styles
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


LOOP_MODES: tuple[str, ...] = ("range", "list", "expression")
_START_END_BOUNDS = (-9999, 9999)
_STEP_BOUNDS = (1, 9999)


def _bounded_int(name: str, low: int, high: int) -> IntParameter:
    param = IntParameter(name)
    param.set_slider_visible(False)
    param.set_line_min(low)
    param.set_line_max(high)
    param.set_commit_on_edit(True)
    param.set_value(max(low, 0))
    return param


def _clamp(value, low: int, high: int) -> int:
    return min(max(int(value), low), high)


class LoopEditor(ParameterForm):
    def __init__(self, parent=None):
        super().__init__(name=NodeType.LOOP.value, parent=parent)
        setup_form(self, nested=True)
        self._index = _labelled(LiveStringParameter("index"), t("form.loop.index"))
        self._mode  = _labelled(ComboParameter("mode"), t("form.loop.mode"))
        self._mode.set_items(dict(zip(
            ("Range", t("form.loop.mode.list"), "Expression"), LOOP_MODES
        )))

        self._start = _labelled(_bounded_int("start", *_START_END_BOUNDS), "Start:")
        self._end   = _labelled(_bounded_int("end", *_START_END_BOUNDS), "End:")
        self._step  = _labelled(_bounded_int("step", *_STEP_BOUNDS), "Step:")
        self._items = _labelled(LiveStringParameter("items"), "")
        self._items.set_area(True)
        self._items.set_placeholder(t("form.loop.items.placeholder"))
        self._expression = _labelled(CodeParameter("expression"), "")
        self._expression.set_placeholder(t("form.loop.expression.placeholder"))

        # The loop expression is always bash -- nothing to connect.
        self._highlighter = PygmentsHighlighter(self._expression.edit.document(), "bash")
        _follow_theme(self._highlighter)

        # One page per mode, in LOOP_MODES order.
        self._stack = QStackedWidget()
        pages = (
            (self._start, self._end, self._step),
            (self._items,),
            (self._expression,),
        )
        for mode, params in zip(LOOP_MODES, pages):
            page = setup_form(ParameterForm(name=mode), nested=True)
            for param in params:
                page.add_parameter(param)
            # Only the expression field fills the page: the others keep their
            # own height (the items area grows with its lines) at the top.
            if mode == "expression":
                stretch_last_row(page)
            self._stack.addWidget(page)

        self._mode.value_changed.connect(
            lambda mode: self._stack.setCurrentIndex(LOOP_MODES.index(mode))
        )

        self.add_parameter(self._index)
        self.add_parameter(self._mode)
        self.add_widget(self._stack)
        stretch_last_row(self)

    def set_data(self, data: dict) -> None:
        """Any mode value other than "list"/"expression" (including
        unrecognized legacy values) selects range, matching _loop_header().
        Numbers are clamped to the field bounds, as the spin boxes used to."""
        self._index.set_value(data.get("index", ""))
        mode = data.get("mode", "range")
        if mode not in LOOP_MODES:
            mode = "range"
        self._mode.set_value(mode)
        # Set it explicitly: assigning the value that is already current emits
        # no signal, so the stack would keep showing the previous page.
        self._stack.setCurrentIndex(LOOP_MODES.index(mode))
        self._start.set_value(_clamp(data.get("start", 0), *_START_END_BOUNDS))
        self._end.set_value(_clamp(data.get("end", 0), *_START_END_BOUNDS))
        self._step.set_value(_clamp(data.get("step", 1), *_STEP_BOUNDS))
        self._items.set_value(data.get("items", ""))
        self._expression.set_value(data.get("expression", ""))

    def get_data(self) -> dict:
        """Every key is returned whatever the active mode, so the inactive
        modes' values survive a round trip through the editor."""
        return {
            "index":      self._index.value(),
            "mode":       self._mode.value(),
            "start":      self._start.value(),
            "end":        self._end.value(),
            "step":       self._step.value(),
            "items":      self._items.value(),
            "expression": self._expression.value(),
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
