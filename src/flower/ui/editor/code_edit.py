from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QTextEdit
from flower.ui.indent import load_indent_width


class CodeEdit(QTextEdit):
    """A monospaced text field whose Tab key inserts spaces.

    Qt would insert a tab character, rendered at its own default width; the
    fields here hold shell and python bodies, where the indentation that ends
    up in the generated script is the one the user sees."""

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Read the width per keystroke rather than caching it: these fields
        are built once per NodeForm and outlive the preferences dialog, so a
        cached value would go stale while the field sits open behind it.
        QSettings keeps its values in memory, so the read costs nothing at
        the scale of a keystroke."""
        if event.key() == Qt.Key.Key_Tab and not self.isReadOnly():
            # isReadOnly() is checked here rather than relied upon: it stops
            # Qt's own key handling, not a programmatic insertText.
            self.textCursor().insertText(" " * load_indent_width())
            return
        super().keyPressEvent(event)
