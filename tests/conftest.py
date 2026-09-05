import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="session", autouse=True)
def catalog():
    """Load a deterministic catalog for the whole test session.

    Imported inside the fixture, not at module level, to keep the Qt import
    order at the top of this file untouched. Without this, t() would return
    bare keys and every UI assertion would compare a key to itself.

    Restores "fr" on teardown so a test that switches to another language
    for its own purposes cannot leak that choice into the rest of the
    session."""
    from flower import i18n
    i18n.load("fr")
    yield
    i18n.load("fr")
