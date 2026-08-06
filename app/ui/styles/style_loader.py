"""Carga y aplicación de la hoja de estilos global de DJPlus."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class StyleApplication(Protocol):
    def setStyleSheet(self, stylesheet: str) -> None:
        """Aplicar una hoja de estilos Qt."""


class GlobalStyleSheetError(RuntimeError):
    """Error al cargar la hoja de estilos global."""


def global_stylesheet_path() -> Path:
    return Path(__file__).with_name("app.qss")


def load_global_stylesheet(path: str | Path | None = None) -> str:
    target = Path(path) if path is not None else global_stylesheet_path()
    try:
        stylesheet = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise GlobalStyleSheetError(
            f"No se pudo cargar la hoja de estilos global: {target}"
        ) from exc
    if not stylesheet.strip():
        raise GlobalStyleSheetError(
            f"La hoja de estilos global está vacía: {target}"
        )
    return stylesheet


def apply_global_stylesheet(
    application: StyleApplication,
    path: str | Path | None = None,
) -> str:
    stylesheet = load_global_stylesheet(path)
    application.setStyleSheet(stylesheet)
    return stylesheet
