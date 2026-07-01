from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QDialog, QGroupBox, QPushButton, QRadioButton,
    QVBoxLayout,
)
from flower.ui.theme import Theme, apply_theme, load_theme, save_theme


class PreferencesDialog(QDialog):
    """Application-wide preferences (theme, and future settings)."""

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

        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(display_group)
        layout.addStretch()
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _set_theme(self, theme: Theme) -> None:
        save_theme(theme)
        apply_theme(QApplication.instance(), theme)
