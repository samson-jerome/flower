import pytest
from PySide6.QtCore import QSettings
from flower.ui import indent as indent_mod
from flower.ui.indent import (
    DEFAULT_INDENT_WIDTH, MAX_INDENT_WIDTH, MIN_INDENT_WIDTH,
    load_indent_width, save_indent_width,
)


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Redirect QSettings() to a throwaway ini file for every test in this module."""
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        indent_mod, "QSettings",
        lambda: QSettings(ini_path, QSettings.Format.IniFormat),
    )


def test_default_is_four_spaces():
    assert DEFAULT_INDENT_WIDTH == 4
    assert load_indent_width() == 4


def test_save_then_load_round_trip():
    save_indent_width(2)
    assert load_indent_width() == 2


def test_a_value_stored_as_text_is_read_back_as_an_int():
    # QSettings hands back strings when it reads an ini file, so the raw
    # value can't go straight to a QTextCursor.insertText multiplier.
    indent_mod.QSettings().setValue("editor/indent_width", "6")
    assert load_indent_width() == 6


def test_a_non_numeric_value_falls_back_to_the_default():
    indent_mod.QSettings().setValue("editor/indent_width", "large")
    assert load_indent_width() == DEFAULT_INDENT_WIDTH


@pytest.mark.parametrize("stored", [0, -3, MAX_INDENT_WIDTH + 1])
def test_a_value_outside_the_bounds_falls_back_to_the_default(stored):
    indent_mod.QSettings().setValue("editor/indent_width", stored)
    assert load_indent_width() == DEFAULT_INDENT_WIDTH


def test_the_bounds_admit_their_own_edges():
    for width in (MIN_INDENT_WIDTH, MAX_INDENT_WIDTH):
        save_indent_width(width)
        assert load_indent_width() == width
