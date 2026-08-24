import pytest
from PySide6.QtCore import QSettings
from flower.engine.execution.runner import DEFAULT_TERMINAL
from flower.app.prefs import terminal


@pytest.fixture(autouse=True)
def clean_settings(qapp, tmp_path):
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path)
    )
    QSettings().clear()
    yield
    QSettings().clear()


def test_load_terminal_falls_back_to_the_engine_default():
    assert terminal.load_terminal() == DEFAULT_TERMINAL


def test_save_then_load_terminal():
    terminal.save_terminal("kitty")
    assert terminal.load_terminal() == "kitty"


def test_a_blank_preference_falls_back_to_the_default():
    terminal.save_terminal("   ")
    assert terminal.load_terminal() == DEFAULT_TERMINAL
