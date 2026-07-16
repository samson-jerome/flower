import pytest
from PySide6.QtCore import QSettings
from flower.ui import interpreters as interpreters_mod
from flower.ui.interpreters import load_interpreters, save_interpreter
from flower.execution.bash_generator import DEFAULT_INTERPRETERS


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Redirect QSettings() to a throwaway ini file for every test in this module."""
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        interpreters_mod, "QSettings",
        lambda: QSettings(ini_path, QSettings.Format.IniFormat),
    )


def test_load_interpreters_defaults_when_nothing_saved():
    assert load_interpreters() == DEFAULT_INTERPRETERS


def test_save_then_load_round_trip():
    save_interpreter("python", "/usr/bin/python3.11")
    result = load_interpreters()
    assert result["python"] == "/usr/bin/python3.11"
    assert result["sh"] == DEFAULT_INTERPRETERS["sh"]
    assert result["powershell"] == DEFAULT_INTERPRETERS["powershell"]
    assert result["javascript"] == DEFAULT_INTERPRETERS["javascript"]
