"""Shared, UI-only feedback primitives for DJPlus workspaces."""
from PySide6.QtWidgets import QLabel, QMessageBox


class FeedbackLabel(QLabel):
    """Small persistent status surface; it never owns domain state."""
    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("feedbackLabel"); self.setWordWrap(True); self.show_info("Listo")
    def _show(self, kind, message):
        self.setProperty("feedbackKind", kind); self.setText(message); self.style().unpolish(self); self.style().polish(self)
    def show_info(self, message): self._show("info", message)
    def show_success(self, message): self._show("success", message)
    def show_warning(self, message): self._show("warning", message)
    def show_error(self, message): self._show("error", message)


def confirm_destructive(parent, title, message):
    """Ask before a destructive UI action; service calls remain unchanged."""
    return QMessageBox.question(parent, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes
