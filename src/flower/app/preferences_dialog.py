from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontMetrics, QPalette
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDialog, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QRadioButton, QSpinBox, QVBoxLayout,
)
from pygments.styles import get_style_by_name
from pygments.token import Token
from flower.i18n import AVAILABLE_LANGUAGES, t
from flower.app.prefs.theme import Theme, apply_theme, load_theme, save_theme
from flower.app.prefs.interpreters import load_interpreters, save_interpreter
from flower.app.prefs.highlight_styles import DARK_STYLES, LIGHT_STYLES, load_style, save_style
from flower.app.prefs.indent import (
    MAX_INDENT_WIDTH, MIN_INDENT_WIDTH, load_indent_width, save_indent_width,
)
from flower.app.prefs.terminal import load_terminal, save_terminal
from flower.app.prefs.editor import load_editor, save_editor
from flower.app.prefs.language import load_language, save_language
from flower.app.editor.code_edit import CodeEdit
from flower.app.editor.highlighter import PygmentsHighlighter

_INTERPRETER_LABELS = {
    "sh":         "Shell (sh)",
    "python":     "Python",
    "powershell": "PowerShell",
    "javascript": "JavaScript (node)",
}


class _StylePreview(CodeEdit):
    """Read-only sample rendered with one explicit Pygments style.

    Unlike the editing fields, which keep the Qt palette, this one paints the
    style's own background: previewing a dark style on a light dialog would
    otherwise show dark text on a light field -- not what the user gets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        # Bash, because it is what both highlighted fields default to. Short
        # enough to stay unobtrusive, varied enough to exercise comment,
        # keyword, string and variable -- the four token families that
        # separate one style from another.
        snippet = t("dialog.prefs.preview_snippet")
        self.setPlainText(snippet)
        lines = snippet.count("\n") + 1
        self.setFixedHeight(QFontMetrics(self.font()).lineSpacing() * lines + 16)
        self._highlighter = PygmentsHighlighter(self.document(), "bash")

    def show_style(self, name: str) -> None:
        self._highlighter.set_style(name)
        style = get_style_by_name(name)
        background = QColor(style.background_color)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, background)
        palette.setColor(QPalette.ColorRole.Text, _base_text_color(style, background))
        self.setPalette(palette)


def _base_text_color(style, background: QColor) -> QColor:
    """Colour for text the style leaves undecorated.

    Most styles declare one on the root token, but not all: `dracula` has a
    dark background and no root colour, so taking the declaration literally
    would render near-black text on near-black. Fall back to contrasting with
    the background instead."""
    declared = style.style_for_token(Token)["color"]
    if declared:
        return QColor(f"#{declared}")
    return QColor("#f0f0f0") if background.lightness() < 128 else QColor("#101010")


class PreferencesDialog(QDialog):
    """Application-wide preferences (theme, script interpreters, and future settings)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("dialog.prefs.title"))

        display_group = QGroupBox(t("dialog.prefs.display"))
        group_layout = QVBoxLayout()
        button_group = QButtonGroup(self)
        self._radios = {
            Theme.LIGHT:  QRadioButton(t("dialog.prefs.theme.light")),
            Theme.DARK:   QRadioButton(t("dialog.prefs.theme.dark")),
            Theme.SYSTEM: QRadioButton(t("dialog.prefs.theme.system")),
        }
        for theme, radio in self._radios.items():
            group_layout.addWidget(radio)
            button_group.addButton(radio)
            radio.toggled.connect(lambda checked, t=theme: checked and self._set_theme(t))
        self._radios[load_theme()].setChecked(True)

        self._language_combo = QComboBox()
        for code, label in AVAILABLE_LANGUAGES.items():
            self._language_combo.addItem(label, code)
        self._language_combo.setCurrentIndex(
            self._language_combo.findData(load_language())
        )
        self._language_notice = QLabel(t("dialog.prefs.language.restart"))
        self._language_notice.setWordWrap(True)
        self._language_notice.setVisible(False)
        # Connected after setCurrentIndex, so preselecting does not fire it
        # and show the notice before the user has chosen anything.
        self._language_combo.currentIndexChanged.connect(self._on_language_changed)

        language_form = QFormLayout()
        language_form.addRow(t("dialog.prefs.language"), self._language_combo)
        group_layout.addLayout(language_form)
        group_layout.addWidget(self._language_notice)
        display_group.setLayout(group_layout)

        interp_group = QGroupBox(t("dialog.prefs.interpreters"))
        interp_form = QFormLayout()
        self._interp_edits: dict[str, QLineEdit] = {}
        interpreters = load_interpreters()
        for lang, label in _INTERPRETER_LABELS.items():
            edit = QLineEdit(interpreters[lang])
            edit.editingFinished.connect(lambda l=lang, e=edit: save_interpreter(l, e.text()))
            interp_form.addRow(t("dialog.prefs.interpreter_row", label=label), edit)
            self._interp_edits[lang] = edit
        interp_group.setLayout(interp_form)

        exec_group = QGroupBox(t("dialog.prefs.exec"))
        exec_form = QFormLayout()
        self._terminal_edit = QLineEdit(load_terminal())
        self._terminal_edit.editingFinished.connect(
            lambda: save_terminal(self._terminal_edit.text())
        )
        exec_form.addRow(t("dialog.prefs.terminal"), self._terminal_edit)
        self._editor_edit = QLineEdit(load_editor())
        self._editor_edit.editingFinished.connect(
            lambda: save_editor(self._editor_edit.text())
        )
        exec_form.addRow(t("dialog.prefs.editor"), self._editor_edit)
        exec_group.setLayout(exec_form)

        highlight_group = QGroupBox(t("dialog.prefs.highlight"))
        highlight_layout = QVBoxLayout()
        self._light_combo, self._light_preview = self._style_row(
            highlight_layout, t("dialog.prefs.highlight.light"), LIGHT_STYLES, dark=False
        )
        self._dark_combo, self._dark_preview = self._style_row(
            highlight_layout, t("dialog.prefs.highlight.dark"), DARK_STYLES, dark=True
        )
        highlight_group.setLayout(highlight_layout)

        edit_group = QGroupBox(t("dialog.prefs.edit"))
        edit_form = QFormLayout()
        self._indent_spin = QSpinBox()
        self._indent_spin.setRange(MIN_INDENT_WIDTH, MAX_INDENT_WIDTH)
        self._indent_spin.setValue(load_indent_width())
        self._indent_spin.setSuffix(t("dialog.prefs.indent.suffix"))
        self._indent_spin.valueChanged.connect(save_indent_width)
        edit_form.addRow(t("dialog.prefs.indent"), self._indent_spin)
        edit_group.setLayout(edit_form)

        close_btn = QPushButton(t("dialog.prefs.close"))
        close_btn.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(display_group)
        layout.addWidget(interp_group)
        layout.addWidget(exec_group)
        layout.addWidget(highlight_group)
        layout.addWidget(edit_group)
        layout.addStretch()
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _style_row(self, layout, label, offered, dark: bool):
        """A style combo and the preview it drives, appended to `layout`."""
        combo = QComboBox()
        combo.addItems(offered)
        combo.setCurrentText(load_style(dark))
        preview = _StylePreview()
        preview.show_style(combo.currentText())

        def on_changed(name: str) -> None:
            preview.show_style(name)
            save_style(dark, name)

        combo.currentTextChanged.connect(on_changed)

        form = QFormLayout()
        form.addRow(label, combo)
        layout.addLayout(form)
        layout.addWidget(preview)
        return combo, preview

    def _set_theme(self, theme: Theme) -> None:
        save_theme(theme)
        apply_theme(QApplication.instance(), theme)

    def _on_language_changed(self, _index: int) -> None:
        save_language(self._language_combo.currentData())
        self._language_notice.setVisible(True)
