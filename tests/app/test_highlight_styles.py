import pytest
from PySide6.QtCore import QSettings
from pygments.styles import get_all_styles
from flower.app.prefs import highlight_styles as styles_mod
from flower.app.prefs.highlight_styles import (
    DARK_STYLES, LIGHT_STYLES, load_style, notifier, save_style,
)


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Redirect QSettings() to a throwaway ini file for every test in this module."""
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        styles_mod, "QSettings",
        lambda: QSettings(ini_path, QSettings.Format.IniFormat),
    )


def test_every_offered_style_exists_in_pygments():
    """The lists are hand-maintained, so a typo or a style dropped by a future
    Pygments release has to fail here rather than at runtime."""
    available = set(get_all_styles())
    assert set(LIGHT_STYLES) <= available
    assert set(DARK_STYLES) <= available


def test_defaults_preserve_the_previous_hard_coded_styles():
    assert LIGHT_STYLES[0] == "default"
    assert DARK_STYLES[0] == "github-dark"


def test_load_style_defaults_when_nothing_saved():
    assert load_style(dark=False) == "default"
    assert load_style(dark=True) == "github-dark"


def test_save_then_load_round_trip():
    save_style(dark=True, name="monokai")
    assert load_style(dark=True) == "monokai"
    assert load_style(dark=False) == "default"


def test_the_two_modes_are_stored_independently():
    save_style(dark=False, name="tango")
    save_style(dark=True, name="dracula")
    assert load_style(dark=False) == "tango"
    assert load_style(dark=True) == "dracula"


def test_unknown_saved_value_falls_back_to_the_default():
    styles_mod.QSettings().setValue("highlight/dark", "no-such-style")
    assert load_style(dark=True) == "github-dark"


def test_a_style_of_the_other_mode_falls_back_to_the_default():
    """`monokai` is a dark style; stored under the light key it would render
    dark-on-light text, so loading rejects it."""
    styles_mod.QSettings().setValue("highlight/light", "monokai")
    assert load_style(dark=False) == "default"


def test_save_style_notifies_listeners():
    seen = []
    slot = lambda: seen.append(True)
    # `notifier` is a module-level singleton: disconnect so the slot doesn't
    # outlive this test and fire on every later save.
    notifier.changed.connect(slot)
    try:
        save_style(dark=True, name="nord")
    finally:
        notifier.changed.disconnect(slot)
    assert seen == [True]
