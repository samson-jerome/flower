import pytest
from PySide6.QtCore import QSettings, QTranslator
from flower.app.prefs import language as language_mod
from flower.app.prefs.language import (
    _language_from_locale, install_qt_translator, load_language, save_language,
)


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Redirect QSettings() to a throwaway ini file for every test here."""
    ini_path = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        language_mod, "QSettings",
        lambda: QSettings(ini_path, QSettings.Format.IniFormat),
    )


def test_save_then_load_round_trip():
    save_language("en")
    assert load_language() == "en"


def test_unset_preference_falls_back_to_system_detection(monkeypatch):
    monkeypatch.setattr(language_mod, "detect_system_language", lambda: "en")
    assert load_language() == "en"


def test_corrupted_preference_falls_back_to_system_detection(monkeypatch):
    language_mod.QSettings().setValue("language", "klingon")
    monkeypatch.setattr(language_mod, "detect_system_language", lambda: "fr")
    assert load_language() == "fr"


def test_a_shipped_locale_is_taken_from_its_first_segment():
    assert _language_from_locale("fr_FR") == "fr"
    assert _language_from_locale("fr")    == "fr"


def test_an_unshipped_locale_falls_back_to_english():
    assert _language_from_locale("de_DE") == "en"
    assert _language_from_locale("C")     == "en"


def test_english_installs_no_qt_translator(qapp):
    # Qt's own source language is English and ships no qtbase_en.qm.
    # Returning False here is the nominal path, not a failure.
    assert install_qt_translator(qapp, "en") is False


def test_french_installs_a_translator_and_keeps_it_referenced(qapp):
    if not install_qt_translator(qapp, "fr"):
        pytest.skip("this PySide6 install ships no qtbase_fr.qm")
    try:
        # Qt does not take ownership: without this reference the translator
        # would be collected and the standard widgets silently revert.
        assert isinstance(qapp._qt_translator, QTranslator)
    finally:
        qapp.removeTranslator(qapp._qt_translator)
        del qapp._qt_translator
