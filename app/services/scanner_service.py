"""Filesystem discovery for the import engine, without persistence or metadata reads."""

from dataclasses import dataclass
from pathlib import Path

from app.services.filepath_normalization import normalize_filepath

DEFAULT_AUDIO_EXTENSIONS = (".mp3", ".wav", ".flac", ".aiff", ".m4a")


@dataclass(frozen=True)
class ScanEvent:
    """A progressive discovery result suitable for a future import queue."""

    event_type: str
    filepath: str | None = None
    error_message: str | None = None


class ScannerService:
    """Discover supported audio files without reading metadata or touching SQLite."""

    def __init__(self, extensions=None):
        configured_extensions = extensions or DEFAULT_AUDIO_EXTENSIONS
        self.extensions = self._normalize_extensions(configured_extensions)

    def discover(self, root_path, cancel_requested=None):
        """Yield file, error, and cancellation events while walking ``root_path``."""
        root = Path(root_path).expanduser()
        if not root.is_dir():
            yield ScanEvent("error", filepath=str(root), error_message="La carpeta raíz no es accesible.")
            return

        pending_directories = [root]
        while pending_directories:
            if self._is_cancelled(cancel_requested):
                yield ScanEvent("cancelled")
                return
            directory = pending_directories.pop()
            try:
                for entry in directory.iterdir():
                    if self._is_cancelled(cancel_requested):
                        yield ScanEvent("cancelled")
                        return
                    try:
                        if entry.is_dir():
                            pending_directories.append(entry)
                        elif entry.is_file() and entry.suffix.casefold() in self.extensions:
                            yield ScanEvent("item", filepath=normalize_filepath(str(entry)))
                    except OSError as error:
                        yield ScanEvent("error", filepath=str(entry), error_message=str(error))
            except OSError as error:
                yield ScanEvent("error", filepath=str(directory), error_message=str(error))

    def _normalize_extensions(self, extensions):
        normalized = set()
        for extension in extensions:
            if not isinstance(extension, str) or not extension.strip():
                raise ValueError("Las extensiones configuradas deben ser texto no vacío.")
            cleaned = extension.strip().casefold()
            normalized.add(cleaned if cleaned.startswith(".") else f".{cleaned}")
        if not normalized:
            raise ValueError("Debe configurarse al menos una extensión de audio.")
        return frozenset(normalized)

    def _is_cancelled(self, cancel_requested):
        return bool(cancel_requested and cancel_requested())
