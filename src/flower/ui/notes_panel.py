from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QTextEdit, QSizePolicy, QSplitter,
)
from PySide6.QtCore import Signal, Qt


class CollapsibleSection(QWidget):
    """Collapsible widget — a header with a checkbox and a content widget.

    The checkbox only hides/shows the content; the header stays visible.
    """

    collapsed_changed = Signal(bool)

    def __init__(self, title: str, content: QWidget, parent=None):
        super().__init__(parent)

        self._toggle = QCheckBox(title)
        self._toggle.setChecked(True)
        self._toggle.toggled.connect(self._on_toggled)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self._toggle)
        header.addStretch()

        self._content = content

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.addLayout(header)
        layout.addWidget(self._content)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    # ── API ──────────────────────────────────────────────────────────────────

    def is_collapsed(self) -> bool:
        return not self._toggle.isChecked()

    def set_collapsed(self, collapsed: bool) -> None:
        if self.is_collapsed() == collapsed:
            return
        # Block the QCheckBox signal to avoid double-firing via _on_toggled,
        # then emit collapsed_changed ourselves so listeners (splitter binding)
        # react to programmatic changes the same as user clicks.
        blocked = self._toggle.blockSignals(True)
        self._toggle.setChecked(not collapsed)
        self._toggle.blockSignals(blocked)
        self._apply_collapsed()
        self.collapsed_changed.emit(collapsed)

    def header_height(self) -> int:
        """Minimum height required to display the header only."""
        # Header height + layout margins (top+bottom)
        m = self.layout().contentsMargins()
        return self._toggle.sizeHint().height() + m.top() + m.bottom()

    def set_theme(self, background: str, text: str | None = None) -> None:
        """Apply a background color to the section (and optionally a text
        color for the header checkbox)."""
        name = f"section_{id(self)}"
        self.setObjectName(name)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        style = f"#{name} {{ background-color: {background}; }}"
        if text:
            style += f" #{name} QCheckBox {{ color: {text}; }}"
        self.setStyleSheet(style)

    # ── Internals ────────────────────────────────────────────────────────────

    def _on_toggled(self, checked: bool) -> None:
        self._apply_collapsed()
        self.collapsed_changed.emit(not checked)

    def _apply_collapsed(self) -> None:
        self._content.setVisible(self._toggle.isChecked())


class NotesPanel(CollapsibleSection):
    """Collapsible free-text widget (description / notes)."""

    text_changed = Signal(str)

    def __init__(self, title: str = "Description", parent=None):
        editor = QTextEdit()
        editor.setPlaceholderText("Add a description...")
        super().__init__(title, editor, parent)
        self._editor = editor
        self._editor.textChanged.connect(
            lambda: self.text_changed.emit(self._editor.toPlainText())
        )

    def text(self) -> str:
        return self._editor.toPlainText()

    def set_text(self, value: str) -> None:
        if value == self._editor.toPlainText():
            return
        blocked = self._editor.blockSignals(True)
        self._editor.setPlainText(value or "")
        self._editor.blockSignals(blocked)


def bind_notes_to_splitter(
    notes: CollapsibleSection,
    splitter: QSplitter,
    index: int = 0,
) -> None:
    """Make `splitter` collapse the section pane to the header height when
    it is unchecked, and restore the previous size when re-checked.

    Stores the last expanded size on the section itself so a single
    splitter can host the panel anywhere along its axis.
    """
    notes._splitter = splitter         # type: ignore[attr-defined]
    notes._splitter_index = index      # type: ignore[attr-defined]
    notes._saved_sizes: list[int] | None = None  # type: ignore[attr-defined]

    def _on_collapsed_changed(collapsed: bool) -> None:
        sizes = list(splitter.sizes())
        if collapsed:
            # Save current expanded layout, then shrink this pane to header.
            notes._saved_sizes = sizes[:]  # type: ignore[attr-defined]
            header = notes.header_height()
            total = sum(sizes)
            shrink = max(0, sizes[index] - header)
            sizes[index] = header
            # Redistribute the freed pixels to the other panes proportionally
            others = [i for i in range(len(sizes)) if i != index]
            others_total = sum(sizes[i] for i in others) or 1
            remaining = total - header
            for i in others:
                sizes[i] = max(1, int(round(remaining * sizes[i] / others_total)))
            splitter.setSizes(sizes)
        else:
            saved = getattr(notes, "_saved_sizes", None)
            if saved and len(saved) == len(sizes) and saved[index] > notes.header_height():
                splitter.setSizes(saved)
            else:
                # No prior expanded size known — give the pane a reasonable share.
                total = sum(sizes) or 1
                fallback = max(120, total // 4)
                sizes[index] = fallback
                splitter.setSizes(sizes)

    notes.collapsed_changed.connect(_on_collapsed_changed)
    # Make sure the splitter does not force the pane fully closed:
    splitter.setCollapsible(index, False)
