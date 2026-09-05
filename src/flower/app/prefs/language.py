from __future__ import annotations
from PySide6.QtCore import QLibraryInfo, QLocale, QSettings, QTranslator
from flower.i18n import AVAILABLE_LANGUAGES

_SETTINGS_KEY = "language"


def _language_from_locale(name: str) -> str:
    """First segment of a locale name (`fr_FR` -> `fr`), or English."""
    code = name.split("_")[0]
    return code if code in AVAILABLE_LANGUAGES else "en"


def detect_system_language() -> str:
    return _language_from_locale(QLocale.system().name())


def load_language() -> str:
    """The language to run in.

    System detection only supplies the initial default: once the user picks
    one explicitly, QSettings wins."""
    value = QSettings().value(_SETTINGS_KEY, "")
    return value if value in AVAILABLE_LANGUAGES else detect_system_language()


def save_language(code: str) -> None:
    QSettings().setValue(_SETTINGS_KEY, code)


def install_qt_translator(app, language: str) -> bool:
    """Align Qt's own standard widgets with `language`.

    The Open/Cancel/Yes/No buttons of QFileDialog and QMessageBox come from
    Qt's catalog, not ours; without this an English UI on a French desktop
    would show a button reading « Annuler ».

    Returns whether a catalog was installed. English is Qt's source
    language, so it carries no real translations -- some PySide6 builds
    ship no qtbase_en.qm at all, others ship an empty placeholder one, and
    either way False is the nominal answer there.
    """
    translator = QTranslator()
    translations = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if not translator.load(f"qtbase_{language}", translations) or translator.isEmpty():
        return False
    app.installTranslator(translator)
    # Qt does not take ownership of the translator. Without a reference it is
    # garbage-collected and the standard widgets revert with no error at all.
    # Same trick as prefs/theme.py uses for its colour-scheme watcher.
    app._qt_translator = translator
    return True
