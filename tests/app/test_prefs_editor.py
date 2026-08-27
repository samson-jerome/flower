import pytest
from PySide6.QtCore import QSettings
from flower.engine.execution.runner import DEFAULT_EDITOR
from flower.app.prefs import editor


@pytest.fixture(autouse=True)
def clean_settings(qapp, tmp_path):
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path)
    )
    QSettings().clear()
    yield
    QSettings().clear()


def test_load_editor_falls_back_to_the_engine_default():
    assert editor.load_editor() == DEFAULT_EDITOR


def test_save_then_load_editor():
    editor.save_editor("subl")
    assert editor.load_editor() == "subl"


def test_a_blank_preference_falls_back_to_the_default():
    editor.save_editor("   ")
    assert editor.load_editor() == DEFAULT_EDITOR
