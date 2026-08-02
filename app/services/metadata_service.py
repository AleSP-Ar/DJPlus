"""Mutagen-backed metadata extraction with no database dependency."""

from dataclasses import dataclass
from pathlib import Path

from mutagen import File


class MetadataReadError(ValueError):
    """Raised when a file cannot provide readable audio metadata."""


@dataclass(frozen=True)
class TrackMetadata:
    title: str
    artist: str
    album: str | None
    genre: str | None
    bpm: float | None
    key: str | None
    duration: float | None
    bitrate: int | None
    sample_rate: int | None


class MetadataService:
    """Read and normalize audio metadata without persisting it."""

    def read(self, filepath):
        path = Path(filepath)
        if not path.is_file():
            raise MetadataReadError("El archivo de audio no existe o no es accesible.")
        try:
            audio = File(path)
        except Exception as error:
            raise MetadataReadError("No se pudo leer la metadata del archivo.") from error
        if audio is None:
            raise MetadataReadError("El archivo no contiene audio compatible.")

        tags = audio.tags or {}
        info = getattr(audio, "info", None)
        return TrackMetadata(
            title=self._text(tags, "TIT2", "title") or path.stem,
            artist=self._text(tags, "TPE1", "artist") or "Unknown",
            album=self._text(tags, "TALB", "album"),
            genre=self._text(tags, "TCON", "genre"),
            bpm=self._number(self._text(tags, "TBPM", "bpm")),
            key=self._text(tags, "TKEY", "initialkey", "key"),
            duration=self._number(getattr(info, "length", None)),
            bitrate=self._integer(getattr(info, "bitrate", None)),
            sample_rate=self._integer(getattr(info, "sample_rate", None)),
        )

    def _text(self, tags, *keys):
        for key in keys:
            value = tags.get(key)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                value = value[0] if value else None
            normalized = str(value).strip() if value is not None else ""
            if normalized:
                return normalized
        return None

    def _number(self, value):
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _integer(self, value):
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
