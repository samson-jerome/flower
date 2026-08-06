from __future__ import annotations
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument
from PySide6.QtWidgets import QApplication
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from pygments.util import ClassNotFound
from flower.ui.theme import is_dark

# Built-in Pygments styles, picked by the background the app currently
# renders on. `github-dark` rather than `monokai`: its reference background
# (#0d1117) is close to our dark QPalette.Base (35, 35, 35) and its colours
# are far less saturated.
_LIGHT_STYLE = "default"
_DARK_STYLE  = "github-dark"

# Language name that means "leave it as plain text".
PLAIN = "text"


class PygmentsHighlighter(QSyntaxHighlighter):
    """Syntax highlighting for a QTextEdit, driven by a Pygments lexer.

    Only the token foreground colour and its bold/italic attributes are
    applied; the style's own background is ignored so the field keeps the
    application's Qt palette for background, caret and selection.

    Tokenising happens on the whole document rather than per block, because
    a single token can cross block boundaries (a bash heredoc, a JavaScript
    /* */ comment). The result is memoised against the document text, so a
    burst of keystrokes costs one tokenisation, not one per block."""

    def __init__(self, document: QTextDocument, language: str = PLAIN) -> None:
        super().__init__(document)
        self._formats: dict = {}
        self._lexer = None
        self._cached_text: str | None = None
        self._cached_spans: list[tuple[int, int, QTextCharFormat]] = []
        self._set_style(_DARK_STYLE if is_dark(QApplication.instance()) else _LIGHT_STYLE)
        self.set_language(language)

    # ── public API ──────────────────────────────────────────────────────────

    def set_language(self, name: str) -> None:
        """Switch lexer. An unknown name, or PLAIN, disables highlighting --
        the field stays plain text and no exception reaches the caller."""
        try:
            self._lexer = None if name == PLAIN else get_lexer_by_name(name)
        except ClassNotFound:
            self._lexer = None
        self._invalidate()

    def refresh_theme(self) -> None:
        """Re-read the style for the palette now in effect. Called on
        construction and on every QApplication.paletteChanged."""
        self._set_style(_DARK_STYLE if is_dark(QApplication.instance()) else _LIGHT_STYLE)

    # ── internals ───────────────────────────────────────────────────────────

    def _set_style(self, style_name: str) -> None:
        """Build one QTextCharFormat per token type the style decorates.
        Token types the style leaves undecorated are omitted, so _format_for
        can simply walk up the hierarchy."""
        self._formats = {}
        for ttype, spec in get_style_by_name(style_name):
            if not (spec["color"] or spec["bold"] or spec["italic"]):
                continue
            fmt = QTextCharFormat()
            if spec["color"]:
                fmt.setForeground(QColor(f"#{spec['color']}"))
            if spec["bold"]:
                fmt.setFontWeight(QFont.Weight.Bold)
            if spec["italic"]:
                fmt.setFontItalic(True)
            self._formats[ttype] = fmt
        self._invalidate()

    def _invalidate(self) -> None:
        self._cached_text = None
        self._cached_spans = []
        self.rehighlight()

    def _format_for(self, ttype) -> QTextCharFormat | None:
        """Walk up the token hierarchy until the style decorates one --
        a style need not carry an entry for every leaf token type."""
        while ttype is not None:
            fmt = self._formats.get(ttype)
            if fmt is not None:
                return fmt
            ttype = ttype.parent
        return None

    def _spans(self) -> list[tuple[int, int, QTextCharFormat]]:
        """(absolute start, length, format) for the whole document, memoised.
        Uses get_tokens_unprocessed, whose indices are absolute positions in
        the source -- get_tokens exposes no positions and applies
        preprocessing filters."""
        text = self.document().toPlainText()
        if text == self._cached_text:
            return self._cached_spans
        spans = []
        if self._lexer is not None:
            for index, ttype, value in self._lexer.get_tokens_unprocessed(text):
                fmt = self._format_for(ttype)
                if fmt is not None and value:
                    spans.append((index, len(value), fmt))
        self._cached_text, self._cached_spans = text, spans
        return spans

    def highlightBlock(self, text: str) -> None:
        spans = self._spans()
        start = self.currentBlock().position()
        end = start + len(text)
        crossing = -1
        for span_start, length, fmt in spans:
            span_end = span_start + length
            if span_end <= start or span_start >= end:
                continue
            self.setFormat(
                max(span_start - start, 0),
                min(span_end, end) - max(span_start, start),
                fmt,
            )
            # `end + 1` is the block's newline: `text` excludes it while some
            # lexers include it in their token (bash puts it in
            # Comment.Single). Comparing against `end` would classify every
            # bash comment line as a crossing.
            if span_end > end + 1:
                crossing = span_start
        self.setCurrentBlockState(crossing)
