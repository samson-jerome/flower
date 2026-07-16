from flower.ui.notes_panel import NotesPanel


def test_notes_panel_starts_expanded(qapp):
    p = NotesPanel()
    assert p.is_collapsed() is False


def test_notes_panel_set_and_get_text(qapp):
    p = NotesPanel()
    p.set_text("hello\nworld")
    assert p.text() == "hello\nworld"


def test_notes_panel_collapse_hides_editor(qapp):
    p = NotesPanel()
    p.set_text("x")
    p.set_collapsed(True)
    assert p.is_collapsed() is True
    assert p._editor.isVisibleTo(p) is False


def test_notes_panel_expand_shows_editor(qapp):
    p = NotesPanel()
    p.set_collapsed(True)
    p.set_collapsed(False)
    assert p.is_collapsed() is False
    assert p._editor.isVisibleTo(p) is True


def test_notes_panel_text_changed_signal(qapp):
    p = NotesPanel()
    received = []
    p.text_changed.connect(received.append)
    p._editor.setPlainText("typed")
    assert received and received[-1] == "typed"


def test_notes_panel_set_text_does_not_emit_when_unchanged(qapp):
    p = NotesPanel()
    p.set_text("same")
    received = []
    p.text_changed.connect(received.append)
    p.set_text("same")
    assert received == []


def test_bind_notes_to_splitter_shrinks_and_restores(qapp):
    from PySide6.QtWidgets import QSplitter, QWidget
    from PySide6.QtCore import Qt
    from flower.ui.notes_panel import bind_notes_to_splitter

    notes = NotesPanel()
    other = QWidget()
    splitter = QSplitter(Qt.Orientation.Vertical)
    splitter.addWidget(notes)
    splitter.addWidget(other)
    splitter.resize(400, 700)
    splitter.setSizes([200, 500])
    splitter.show()
    qapp.processEvents()
    bind_notes_to_splitter(notes, splitter, index=0)

    sizes_before = splitter.sizes()
    total_before = sum(sizes_before)
    assert sizes_before[0] > notes.header_height()

    # Collapse: notes pane shrinks to roughly the header height.
    notes.set_collapsed(True)
    qapp.processEvents()
    sizes_collapsed = splitter.sizes()
    assert sizes_collapsed[0] <= notes.header_height() + 4
    assert sizes_collapsed[1] > sizes_collapsed[0]
    # Splitter preserves total length when redistributing.
    assert sum(sizes_collapsed) == total_before

    # Expand: previous sizes restored.
    notes.set_collapsed(False)
    qapp.processEvents()
    assert splitter.sizes() == sizes_before


def test_tinted_icon_recolors_svg_pixels(qapp):
    from flower.ui.notes_panel import _tinted_icon, _ICON_EXPANDED

    icon = _tinted_icon(_ICON_EXPANDED, "#ff0000")
    image = icon.pixmap(16, 16).toImage()

    found_colored_pixel = False
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() > 0:
                found_colored_pixel = True
                assert color.red() > 200
                assert color.green() < 50
                assert color.blue() < 50
    assert found_colored_pixel


def test_tinted_icon_differs_by_color(qapp):
    from flower.ui.notes_panel import _tinted_icon, _ICON_EXPANDED

    red_image = _tinted_icon(_ICON_EXPANDED, "#ff0000").pixmap(16, 16).toImage()
    green_image = _tinted_icon(_ICON_EXPANDED, "#00ff00").pixmap(16, 16).toImage()
    assert red_image != green_image


def test_notes_panel_icon_changes_on_collapse(qapp):
    p = NotesPanel()
    expanded_icon_key = p._toggle.icon().cacheKey()

    p.set_collapsed(True)
    collapsed_icon_key = p._toggle.icon().cacheKey()

    assert expanded_icon_key != collapsed_icon_key


def test_notes_panel_header_is_checkable_button(qapp):
    from PySide6.QtWidgets import QPushButton

    p = NotesPanel()
    assert isinstance(p._toggle, QPushButton)
    assert p._toggle.isCheckable() is True
