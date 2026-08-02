from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from ..services.collection_service import CollectionService
    from ..services.smart_collection_service import SmartCollectionService
except ImportError:  # pragma: no cover - fallback for direct execution
    from app.services.collection_service import CollectionService
    from app.services.smart_collection_service import SmartCollectionService


class CollectionPanel(QWidget):
    """Small UI surface for manual collection administration."""

    def __init__(self):
        super().__init__()
        self.collection_service = CollectionService()
        self.smart_collection_service = SmartCollectionService(collection_service=self.collection_service)
        self.selected_collection_id = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Colecciones"))

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nombre de colección")
        self.name_input.returnPressed.connect(self.create_collection)
        layout.addWidget(self.name_input)

        self.collection_list = QListWidget()
        self.collection_list.itemSelectionChanged.connect(self.select_collection)
        layout.addWidget(self.collection_list)

        buttons = QHBoxLayout()
        create_button = QPushButton("Crear")
        create_button.clicked.connect(self.create_collection)
        create_smart_button = QPushButton("Crear Smart")
        create_smart_button.clicked.connect(self.create_smart_collection)
        rename_button = QPushButton("Renombrar")
        rename_button.clicked.connect(self.rename_collection)
        delete_button = QPushButton("Eliminar")
        delete_button.clicked.connect(self.delete_collection)
        buttons.addWidget(create_button)
        buttons.addWidget(create_smart_button)
        buttons.addWidget(rename_button)
        buttons.addWidget(delete_button)
        layout.addLayout(buttons)

        self.status = QLabel("Selecciona una colección")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.rules_label = QLabel("")
        self.rules_label.setWordWrap(True)
        layout.addWidget(self.rules_label)

    def refresh(self, select_id=None):
        selected_id = self.selected_collection_id if select_id is None else select_id
        self.collection_list.blockSignals(True)
        self.collection_list.clear()
        selected_item = None
        for collection in self.collection_service.list_collections():
            item = QListWidgetItem(collection.name)
            item.setData(Qt.UserRole, collection.id)
            self.collection_list.addItem(item)
            if collection.id == selected_id:
                selected_item = item
        self.collection_list.blockSignals(False)
        if selected_item is not None:
            self.collection_list.setCurrentItem(selected_item)
            self.select_collection()
        else:
            self.selected_collection_id = None
            self.status.setText("Selecciona una colección")

    def create_collection(self):
        try:
            collection = self.collection_service.create_collection(self.name_input.text())
        except ValueError as error:
            self.status.setText(str(error))
            return
        self.name_input.clear()
        self.refresh(select_id=collection.id)

    def create_smart_collection(self):
        try:
            collection = self.smart_collection_service.create_smart_collection(self.name_input.text())
        except ValueError as error:
            self.status.setText(str(error))
            return
        self.name_input.clear()
        self.refresh(select_id=collection.id)

    def rename_collection(self):
        if self.selected_collection_id is None:
            self.status.setText("Selecciona una colección para renombrarla.")
            return
        try:
            collection = self.collection_service.rename_collection(
                self.selected_collection_id,
                self.name_input.text(),
            )
        except ValueError as error:
            self.status.setText(str(error))
            return
        self.name_input.clear()
        self.refresh(select_id=collection.id)

    def delete_collection(self):
        if self.selected_collection_id is None:
            self.status.setText("Selecciona una colección para eliminarla.")
            return
        self.collection_service.delete_collection(self.selected_collection_id)
        self.refresh()

    def select_collection(self):
        item = self.collection_list.currentItem()
        if item is None:
            self.selected_collection_id = None
            self.status.setText("Selecciona una colección")
            self.rules_label.setText("")
            return
        self.selected_collection_id = item.data(Qt.UserRole)
        count = self.collection_service.count_tracks(self.selected_collection_id)
        collection = self.collection_service.get_collection(self.selected_collection_id)
        if collection.type == "smart":
            rules = self.smart_collection_service.list_rules(collection.id)
            rendered_rules = " AND ".join(
                f"{rule.field} {rule.operator} {rule.value}" for rule in rules
            ) or "Sin reglas (todas las pistas)"
            self.status.setText(f"{item.text()}: colección smart")
            self.rules_label.setText(f"Reglas: {rendered_rules}")
        else:
            self.status.setText(f"{item.text()}: {count} pistas")
            self.rules_label.setText("")

    def closeEvent(self, event):
        self.collection_service.close()
        self.smart_collection_service.close()
        super().closeEvent(event)
