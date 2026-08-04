"""Qt application fixtures shared by tests that construct widgets.

The helper deliberately refuses to treat a ``QCoreApplication`` as a
``QApplication``: a QWidget may only be created under the latter.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


class IncompatibleQtApplicationError(RuntimeError):
    """Raised when a process already owns a non-GUI Qt application."""


_application_reference: QApplication | None = None


def ensure_qapplication(
    *,
    instance_getter: Callable[[], Any] | None = None,
    application_factory: Callable[[list[str]], QApplication] | None = None,
    application_type: type[QApplication] = QApplication,
) -> QApplication:
    """Return the process QApplication or create one when no app exists.

    Test-only injection points make the incompatible-QCoreApplication contract
    unit-testable without ever constructing a QWidget under that invalid state.
    """

    global _application_reference
    get_instance = instance_getter or QCoreApplication.instance
    create_application = application_factory or application_type
    existing = get_instance()
    if existing is None:
        application = create_application([])
    elif isinstance(existing, application_type):
        application = existing
    else:
        raise IncompatibleQtApplicationError(
            "Existe una QCoreApplication incompatible; los tests con QWidget "
            "deben iniciarse con QApplication."
        )
    _application_reference = application
    return application
