import sys

from PySide6.QtWidgets import QApplication

try:
    from .database import init_database
    from .ui.main_window import MainWindow
except ImportError:  # pragma: no cover - fallback for direct execution
    from database import init_database
    from ui.main_window import MainWindow


def main():
    init_database()

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
