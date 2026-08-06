from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTextEdit
from PySide6.QtGui import QColor
from pygments.token import Token
from flower.ui.editor.highlighter import PygmentsHighlighter


def _edit(language, text):
    """A QTextEdit with a highlighter attached, already populated."""
    edit = QTextEdit()
    highlighter = PygmentsHighlighter(edit.document(), language)
    edit.setPlainText(text)
    return edit, highlighter


def _block_colors(edit, block_number):
    """Colours actually applied to one block of the document -- proof the
    formats reached the document, not just the span list."""
    block = edit.document().findBlockByNumber(block_number)
    return {r.format.foreground().color().name() for r in block.layout().formats()}


def test_python_body_colors_keyword_string_and_comment(qapp):
    edit, hl = _edit("python", '# note\nimport os\ns = "x"\n')
    assert hl._spans()
    colors = _block_colors(edit, 0) | _block_colors(edit, 1) | _block_colors(edit, 2)
    assert len(colors) >= 3, colors


def test_unknown_language_yields_no_spans(qapp):
    _, hl = _edit("klingon", "qapla'\n")
    assert hl._spans() == []


def test_text_language_yields_no_spans(qapp):
    _, hl = _edit("text", "juste du texte\n")
    assert hl._spans() == []


def test_bash_heredoc_colors_every_line_it_spans(qapp):
    # The bash lexer emits the whole heredoc as one token crossing three blocks.
    edit, _ = _edit("bash", "cat <<EOF\nligne1\nEOF\n")
    assert _block_colors(edit, 0)
    assert _block_colors(edit, 1)
    assert _block_colors(edit, 2)


def test_javascript_block_comment_colors_both_lines(qapp):
    edit, _ = _edit("javascript", "/* a\nb */\nlet x = 1\n")
    assert _block_colors(edit, 0)
    assert _block_colors(edit, 1)


def test_python_triple_quote_colors_every_line(qapp):
    # Complementary case: the Python lexer emits one token per line rather
    # than a single crossing token, so the spans must still cover all three.
    edit, _ = _edit("python", 's = """a\nb\nc"""\n')
    assert _block_colors(edit, 0)
    assert _block_colors(edit, 1)
    assert _block_colors(edit, 2)


def test_block_state_reports_the_crossing_span_start(qapp):
    edit, _ = _edit("bash", "cat <<EOF\nligne1\nEOF\n")
    doc = edit.document()
    # The heredoc token starts at offset 4 and crosses blocks 0 and 1.
    assert doc.findBlockByNumber(0).userState() == 4
    assert doc.findBlockByNumber(1).userState() == 4
    assert doc.findBlockByNumber(2).userState() == -1


def test_bash_comment_is_not_reported_as_crossing(qapp):
    # The bash lexer includes the trailing newline in Comment.Single, while
    # highlightBlock's `text` excludes it -- comparing against `end` instead
    # of `end + 1` would classify every bash comment line as a crossing.
    edit, _ = _edit("bash", "# fin\necho ok\n")
    assert edit.document().findBlockByNumber(0).userState() == -1


def test_format_is_inherited_from_a_parent_token_type(qapp):
    # A style need not define every leaf token type; the lookup walks up.
    _, hl = _edit("python", "x = 1\n")
    assert hl._format_for(Token.Literal.Number.Integer) is not None


def test_theme_refresh_changes_colors(qapp):
    _, hl = _edit("python", "import os\n")
    hl._set_style("default")
    light = hl._format_for(Token.Keyword).foreground().color().name()
    hl._set_style("github-dark")
    dark = hl._format_for(Token.Keyword).foreground().color().name()
    assert light != dark
    assert QColor(light).isValid() and QColor(dark).isValid()


def test_set_language_reruns_the_lexer(qapp):
    edit, hl = _edit("text", "import os\n")
    assert hl._spans() == []
    hl.set_language("python")
    assert hl._spans()
    hl.set_language("text")
    assert hl._spans() == []


def test_spans_are_recomputed_after_an_edit(qapp):
    edit, hl = _edit("python", "x = 1\n")
    before = len(hl._spans())
    edit.setPlainText("import os\nimport sys\n")
    assert len(hl._spans()) != before


def test_background_is_left_to_the_qt_palette(qapp):
    # The style's own bgcolor must not be applied -- the field keeps the
    # application's palette for background, caret and selection. Test the
    # brush style, not the colour: an unset background still reports a valid
    # (black) colour, so only NoBrush proves nothing is painted.
    _, hl = _edit("python", "import os\n")
    assert hl._format_for(Token.Keyword).background().style() == Qt.BrushStyle.NoBrush
