from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget
from .feedback import confirm_destructive

try:
    from ..services.collection_service import CollectionService
    from ..services.smart_collection_service import SmartCollectionService
except ImportError:  # pragma: no cover
    from app.services.collection_service import CollectionService
    from app.services.smart_collection_service import SmartCollectionService


class CollectionPanel(QWidget):
    """Collection administration surface; collection rules remain service-owned."""

    def __init__(self, collection_service=None, smart_collection_service=None):
        super().__init__()
        self.collection_service = collection_service or CollectionService()
        self.smart_collection_service = smart_collection_service or SmartCollectionService(collection_service=self.collection_service)
        self.selected_collection_id = None
        self._build_ui(); self.refresh()

    def _build_ui(self):
        self.setObjectName("collectionsPanel")
        self.setStyleSheet("QFrame#collectionToolbar,QFrame#collectionSection { background:#1f2937; border:1px solid #374151; border-radius:8px; } QLabel#collectionTitle { font-size:18px; font-weight:600; } QLabel#collectionHint,QLabel#collectionEmpty { color:#9ca3af; } QPushButton#collectionPrimary { background:#2563eb; color:white; font-weight:600; }")
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(12)
        title = QLabel("Colecciones"); title.setObjectName("collectionTitle"); layout.addWidget(title)
        hint = QLabel("Organizá selecciones manuales y reglas inteligentes sin mezclar sus flujos."); hint.setObjectName("collectionHint"); layout.addWidget(hint)
        toolbar = QFrame(); toolbar.setObjectName("collectionToolbar"); tools = QHBoxLayout(toolbar); tools.setContentsMargins(10, 10, 10, 10); tools.setSpacing(8)
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("Buscar colecciones"); self.search_input.setClearButtonEnabled(True); self.search_input.setAccessibleName("Buscar colecciones"); self.search_input.textChanged.connect(self.refresh)
        self.name_input = QLineEdit(); self.name_input.setPlaceholderText("Nombre de colección"); self.name_input.setAccessibleName("Nombre de colección"); self.name_input.returnPressed.connect(self.create_collection)
        self.create_button = QPushButton("Crear"); self.create_button.setObjectName("collectionPrimary"); self.create_button.clicked.connect(self.create_collection)
        self.create_smart_button = QPushButton("Nueva inteligente"); self.create_smart_button.clicked.connect(self.create_smart_collection)
        self.rename_button = QPushButton("Renombrar"); self.rename_button.clicked.connect(self.rename_collection)
        self.delete_button = QPushButton("Eliminar"); self.delete_button.clicked.connect(self.delete_collection)
        for widget in (self.search_input, self.name_input, self.create_button, self.create_smart_button, self.rename_button, self.delete_button): tools.addWidget(widget)
        tools.addStretch(1); layout.addWidget(toolbar)
        self.collection_list = self._add_section(layout, "Manuales", "No hay colecciones manuales.")
        self.smart_collection_list = self._add_section(layout, "Inteligentes", "No hay colecciones inteligentes.")
        self.status = QLabel("Seleccioná una colección"); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.rules_label = QLabel(""); self.rules_label.setWordWrap(True); layout.addWidget(self.rules_label)

    def _add_section(self, parent, title, empty):
        frame = QFrame(); frame.setObjectName("collectionSection"); section = QVBoxLayout(frame); section.setContentsMargins(12, 10, 12, 10); section.setSpacing(6)
        section.addWidget(QLabel(title))
        listing = QListWidget(); listing.setAccessibleName(f"Colecciones {title.lower()}"); listing.itemSelectionChanged.connect(lambda source=listing: self.select_collection(source)); section.addWidget(listing)
        placeholder = QLabel(empty); placeholder.setObjectName("collectionEmpty"); placeholder.setAlignment(Qt.AlignCenter); placeholder.setMinimumHeight(36); listing.empty_placeholder = placeholder; section.addWidget(placeholder)
        parent.addWidget(frame); return listing

    def refresh(self, _text=None, select_id=None):
        selected_id = self.selected_collection_id if select_id is None else select_id; query = self.search_input.text().casefold().strip()
        lists = ((self.collection_list, "manual"), (self.smart_collection_list, "smart")); selected_item = None
        for listing, kind in lists:
            listing.blockSignals(True); listing.clear()
            for collection in self.collection_service.list_collections():
                if collection.type != kind or query and query not in collection.name.casefold(): continue
                item = QListWidgetItem(collection.name); item.setData(Qt.UserRole, collection.id); listing.addItem(item)
                if collection.id == selected_id: selected_item = item
            listing.empty_placeholder.setVisible(listing.count() == 0); listing.blockSignals(False)
        if selected_item is not None:
            selected_item.listWidget().setCurrentItem(selected_item); self.select_collection(selected_item.listWidget())
        else:
            self.selected_collection_id = None; self.status.setText("Sin resultados" if query else "Seleccioná una colección"); self.rules_label.setText("")

    def create_collection(self): self._create(self.collection_service.create_collection)
    def create_smart_collection(self): self._create(self.smart_collection_service.create_smart_collection)
    def _create(self, creator):
        try: collection = creator(self.name_input.text())
        except ValueError as error: self.status.setText(str(error)); return
        self.name_input.clear(); self.refresh(select_id=collection.id)
    def rename_collection(self):
        if self.selected_collection_id is None: self.status.setText("Seleccioná una colección para renombrarla."); return
        try: collection = self.collection_service.rename_collection(self.selected_collection_id, self.name_input.text())
        except ValueError as error: self.status.setText(str(error)); return
        self.name_input.clear(); self.refresh(select_id=collection.id)
    def delete_collection(self):
        if self.selected_collection_id is None: self.status.setText("Seleccioná una colección para eliminarla."); return
        if not confirm_destructive(self, "Eliminar colección", "Esta acción eliminará la colección seleccionada."):
            self.status.setText("Eliminación cancelada."); return
        self.collection_service.delete_collection(self.selected_collection_id); self.refresh()
    def select_collection(self, source=None):
        item = (source or self.sender()).currentItem()
        if item is None: return
        other = self.smart_collection_list if item.listWidget() is self.collection_list else self.collection_list; other.blockSignals(True); other.clearSelection(); other.blockSignals(False)
        self.selected_collection_id = item.data(Qt.UserRole); count = self.collection_service.count_tracks(self.selected_collection_id); collection = self.collection_service.get_collection(self.selected_collection_id)
        if collection.type == "smart":
            rules = self.smart_collection_service.list_rules(collection.id); rendered = " AND ".join(f"{rule.field} {rule.operator} {rule.value}" for rule in rules) or "Sin reglas (todas las pistas)"
            self.status.setText(f"{item.text()}: colección inteligente · {count} pistas"); self.rules_label.setText(f"Reglas: {rendered}")
        else: self.status.setText(f"{item.text()}: colección manual · {count} pistas"); self.rules_label.setText("")
    def closeEvent(self, event):
        self.collection_service.close(); self.smart_collection_service.close(); super().closeEvent(event)
