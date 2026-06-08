import sys
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from flower.ui.main_window import MainWindow


ICON_PATH = Path(__file__).resolve().parents[2] / "assets" / "app-icon.png"


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Flower")
    app.setDesktopFileName("flower")
    icon = QIcon(str(ICON_PATH))
    app.setWindowIcon(icon)
    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
