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
