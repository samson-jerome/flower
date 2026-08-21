import sys
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from flower.app.main_window import MainWindow
from flower.app.theme import apply_theme, load_theme, watch_system_theme


ICON_PATH = Path(__file__).resolve().parents[3] / "assets" / "app-icon.png"


def main() -> None:
    app = QApplication(sys.argv)
    app.setOrganizationName("Flower")
    app.setApplicationName("Flower")
    app.setDesktopFileName("flower")
    apply_theme(app, load_theme())
    watch_system_theme(app)
    icon = QIcon(str(ICON_PATH))
    app.setWindowIcon(icon)
    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
