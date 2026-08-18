from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent, QTextCursor
from PySide6.QtWidgets import QTextEdit
from flower.ui.indent import load_indent_width


def _indent_level_size(text: str, width: int) -> int:
    """How many characters at the start of `text` make up one indent level.

    A leading tab counts as a level on its own: a .flow written before Tab
    inserted spaces still holds real tab characters, and dedenting those
    lines has to work too."""
    if text.startswith("\t"):
        return 1
    return min(len(text) - len(text.lstrip(" ")), width)


class CodeEdit(QTextEdit):
    """A monospaced text field with code-style indentation.

    Qt would insert a tab character, rendered at its own default width; the
    fields here hold shell and python bodies, where the indentation that ends
    up in the generated script is the one the user sees. Tab inserts spaces
    instead -- across every selected line when the selection spans more than
    one -- and Shift+Tab takes a level back off."""

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """isReadOnly() is checked here rather than relied upon: it stops
        Qt's own key handling, not the programmatic edits below."""
        if self.isReadOnly():
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Backtab:
            self._dedent()
            return
        if event.key() == Qt.Key.Key_Tab:
            self._indent()
            return
        super().keyPressEvent(event)

    # ── internals ───────────────────────────────────────────────────────────

    def _indent(self) -> None:
        """A multi-line selection is indented line by line. Anything else --
        no selection, or one within a single line -- keeps Qt's own meaning
        for a character key: insert it, replacing the selection if any.

        The width is read per keystroke rather than cached: these fields are
        built once per NodeForm and outlive the preferences dialog, so a
        cached value would go stale while a field sits open behind it.
        QSettings keeps its values in memory, so the read costs nothing at
        the scale of a keystroke."""
        pad = " " * load_indent_width()
        first, last = self._selected_line_range()
        if first == last:
            self.textCursor().insertText(pad)
            return
        self._edit_line_starts(first, last, lambda _text: (0, pad))

    def _dedent(self) -> None:
        """Take one level off every selected line, or off the cursor's line
        when nothing is selected."""
        width = load_indent_width()
        first, last = self._selected_line_range()
        self._edit_line_starts(
            first, last, lambda text: (_indent_level_size(text, width), "")
        )

    def _selected_line_range(self) -> tuple[int, int]:
        """Block numbers the selection covers, the cursor's own block when
        there is no selection.

        A selection ending at column 0 of a block does not reach into it, so
        that block is left out -- the usual convention for a selection
        dragged just past a line break."""
        cursor = self.textCursor()
        document = self.document()
        first = document.findBlock(cursor.selectionStart())
        last = document.findBlock(cursor.selectionEnd())
        if last != first and last.position() == cursor.selectionEnd():
            last = last.previous()
        return first.blockNumber(), last.blockNumber()

    def _edit_line_starts(self, first: int, last: int, edit) -> None:
        """Apply `edit(line_text) -> (chars_removed, text_inserted)` at column
        0 of every line in the range.

        The whole run is one edit block, so a single Ctrl+Z takes back the
        indentation of the block rather than one line at a time. A selection
        is restored over whole lines afterwards -- otherwise pressing Tab
        twice in a row would mean re-selecting in between."""
        cursor = self.textCursor()
        had_selection = cursor.hasSelection()
        document = self.document()

        cursor.beginEditBlock()
        for number in range(first, last + 1):
            block = document.findBlockByNumber(number)
            removed, inserted = edit(block.text())
            if not removed and not inserted:
                continue
            cursor.setPosition(block.position())
            if removed:
                cursor.setPosition(
                    block.position() + removed, QTextCursor.MoveMode.KeepAnchor
                )
            cursor.insertText(inserted)
        cursor.endEditBlock()

        if had_selection:
            first_block = document.findBlockByNumber(first)
            last_block = document.findBlockByNumber(last)
            cursor.setPosition(first_block.position())
            # length() counts the block separator, which is not part of the line.
            cursor.setPosition(
                last_block.position() + last_block.length() - 1,
                QTextCursor.MoveMode.KeepAnchor,
            )
            self.setTextCursor(cursor)
