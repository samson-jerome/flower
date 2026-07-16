from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QDialog, QFormLayout, QGroupBox, QLineEdit,
    QPushButton, QRadioButton, QVBoxLayout,
)
from flower.ui.theme import Theme, apply_theme, load_theme, save_theme
from flower.ui.interpreters import load_interpreters, save_interpreter

_INTERPRETER_LABELS = {
    "sh":         "Shell (sh)",
    "python":     "Python",
    "powershell": "PowerShell",
    "javascript": "JavaScript (node)",
}


class PreferencesDialog(QDialog):
    """Application-wide preferences (theme, script interpreters, and future settings)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Préférences")

        display_group = QGroupBox("Affichage")
        group_layout = QVBoxLayout()
        button_group = QButtonGroup(self)
        self._radios = {
            Theme.LIGHT:  QRadioButton("Clair"),
            Theme.DARK:   QRadioButton("Sombre"),
            Theme.SYSTEM: QRadioButton("Suivre le système"),
        }
        for theme, radio in self._radios.items():
            group_layout.addWidget(radio)
            button_group.addButton(radio)
            radio.toggled.connect(lambda checked, t=theme: checked and self._set_theme(t))
        self._radios[load_theme()].setChecked(True)
        display_group.setLayout(group_layout)

        interp_group = QGroupBox("Interprètes")
        interp_form = QFormLayout()
        self._interp_edits: dict[str, QLineEdit] = {}
        interpreters = load_interpreters()
        for lang, label in _INTERPRETER_LABELS.items():
            edit = QLineEdit(interpreters[lang])
            edit.editingFinished.connect(lambda l=lang, e=edit: save_interpreter(l, e.text()))
            interp_form.addRow(f"{label} :", edit)
            self._interp_edits[lang] = edit
        interp_group.setLayout(interp_form)

        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(display_group)
        layout.addWidget(interp_group)
        layout.addStretch()
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _set_theme(self, theme: Theme) -> None:
        save_theme(theme)
        apply_theme(QApplication.instance(), theme)
