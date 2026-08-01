from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
)

try:
    from .library_view import LibraryView
except ImportError:  # pragma: no cover - fallback for direct execution
    from ui.library_view import LibraryView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("DJPlus")
        self.resize(1000, 600)

        self.create_ui()

    def create_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("DJPlus - Music Library Manager")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)

        library = LibraryView()
        layout.addWidget(library)

        self.setCentralWidget(central)
