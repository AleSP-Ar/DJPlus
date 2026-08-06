from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class ContextHeader(QFrame):
    """Reusable header component for the application shell."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("contextHeader")
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(8)

        identity = QVBoxLayout()
        identity.setSpacing(2)
        self.appTitle = QLabel("DJPlus")
        self.appTitle.setObjectName("appTitle")
        self.appTitle.setAccessibleName("Título de la aplicación")
        self.appSubtitle = QLabel("Biblioteca musical")
        self.appSubtitle.setObjectName("appSubtitle")
        self.appSubtitle.setAccessibleName("Descripción de la aplicación")
        identity.addWidget(self.appTitle)
        identity.addWidget(self.appSubtitle)

        layout.addLayout(identity)
        layout.addStretch(1)

        self.page_title_label = QLabel()
        self.page_title_label.setObjectName("pageTitle")
        self.page_title_label.setAccessibleName("Título de sección actual")
        layout.addWidget(self.page_title_label, alignment=Qt.AlignRight | Qt.AlignVCenter)

    def set_page_title(self, title: str):
        self.page_title_label.setText(title)
