from typing import Iterable, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton


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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        for key, label in self._sections:
            btn = QPushButton(label)
            btn.setObjectName(f"navigation_{key}")
            btn.setCheckable(True)
            btn.setAccessibleName(f"Ir a {label}")
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
