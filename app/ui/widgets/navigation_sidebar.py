from typing import Iterable, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QPushButton


class NavigationSidebar(QFrame):
    """Reusable navigation rail.

    - `sections` is an iterable of `(key, label)` tuples.
    - Emits `section_requested` with the section key when a button is activated.
    - Provides `set_current_section(key)` to update checked state.
    - Exposes `buttons` mapping of key -> QPushButton for external access.
    """

    section_requested = Signal(str)

    def __init__(self, sections: Iterable[Tuple[str, str]]):
        super().__init__()
        self.setObjectName("navigationRail")
        self.buttons: dict[str, QPushButton] = {}
        self._sections = list(sections)
        self._compact = False
        self._compact = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(6)

        identity = QHBoxLayout()
        brand = QLabel("DJ+")
        brand.setObjectName("navigationBrand")
        brand.setAccessibleName("DJPlus")
        identity.addWidget(brand)
        identity.addStretch(1)
        layout.addLayout(identity)

        for key, label in self._sections:
            btn = QPushButton(label)
            btn.setObjectName(f"navigation_{key}")
            btn.setCheckable(True)
            btn.setAccessibleName(f"Ir a {label}")
            btn.setToolTip(label)
            btn.setProperty("navigationLabel", label)
            btn.setToolTip(label)
            btn.setProperty("navigationLabel", label)
            btn.clicked.connect(lambda _checked=False, k=key: self.section_requested.emit(k))
            layout.addWidget(btn)
            self.buttons[key] = btn

        layout.addStretch(1)

    def set_current_section(self, key: str) -> None:
        """Mark the provided section button as checked and unset others.

        Raises ValueError for unknown keys.
        """
        if key not in self.buttons:
            raise ValueError(f"Sección desconocida: {key}")
        for k, btn in self.buttons.items():
            btn.setChecked(k == key)

    def set_compact(self, compact: bool) -> None:
        """Keep every destination reachable when the shell becomes narrow."""
        compact = bool(compact)
        if compact == self._compact:
            return
        self._compact = compact
        for key, button in self.buttons.items():
            label = str(button.property("navigationLabel"))
            button.setText(self._compact_label(key, label) if compact else label)
        self.setMinimumWidth(58 if compact else 142)
        self.setMaximumWidth(58 if compact else 164)

    @staticmethod
    def _compact_label(key: str, label: str) -> str:
        abbreviations = {
            "library": "B", "collections": "C", "playlists": "P", "dj_set": "DJ",
            "import": "I", "metadata": "M", "assistant": "A", "settings": "⚙",
        }
        return abbreviations.get(key, label[:1].upper())

    def set_compact(self, compact: bool) -> None:
        """Keep every destination reachable when the shell becomes narrow."""
        compact = bool(compact)
        if compact == self._compact:
            return
        self._compact = compact
        for key, button in self.buttons.items():
            label = str(button.property("navigationLabel"))
            button.setText(self._compact_label(key, label) if compact else label)
        self.setMinimumWidth(58 if compact else 142)
        self.setMaximumWidth(58 if compact else 164)

    @staticmethod
    def _compact_label(key: str, label: str) -> str:
        abbreviations = {
            "library": "B", "collections": "C", "playlists": "P", "dj_set": "DJ",
            "import": "I", "metadata": "M", "assistant": "A", "settings": "⚙",
        }
        return abbreviations.get(key, label[:1].upper())
