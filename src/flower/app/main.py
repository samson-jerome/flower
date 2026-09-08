import argparse
import sys
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from flower import i18n
from flower.app.main_window import MainWindow
from flower.app.prefs.language import install_qt_translator, load_language
from flower.app.prefs.theme import apply_theme, load_theme, watch_system_theme
from flower.version import get_version


ICON_PATH = Path(__file__).resolve().parents[3] / "assets" / "app-icon.png"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="flower", description="Éditeur de graphes d'exécution."
    )
    parser.add_argument("--version", action="version", version=f"flower {get_version()}")
    # parse_known_args, not parse_args: QApplication interprets Qt's own
    # arguments (-style, -platform...), and a strict parser would reject them.
    # Unknown arguments carry on to Qt exactly as they did before.
    _, qt_args = parser.parse_known_args()

    app = QApplication([sys.argv[0], *qt_args])
    app.setOrganizationName("Flower")
    app.setApplicationName("Flower")
    app.setDesktopFileName("flower")
    apply_theme(app, load_theme())
    watch_system_theme(app)
    # Before MainWindow(): widgets resolve their strings as they are built,
    # and the language only changes on restart.
    language = load_language()
    i18n.load(language)
    install_qt_translator(app, language)
    icon = QIcon(str(ICON_PATH))
    app.setWindowIcon(icon)
    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
