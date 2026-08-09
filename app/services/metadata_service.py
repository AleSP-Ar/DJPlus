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
        path, audio = self._open_audio(filepath)
        embedded = self.read_embedded(filepath, path=path, audio=audio)
        info = getattr(audio, "info", None)
        return TrackMetadata(
            title=embedded.title or path.stem,
            artist=embedded.artist or "Unknown",
            album=embedded.album,
            genre=embedded.genre,
            bpm=embedded.bpm,
            key=embedded.key,
            duration=self._number(getattr(info, "length", None)),
            bitrate=self._integer(getattr(info, "bitrate", None)),
            sample_rate=self._integer(getattr(info, "sample_rate", None)),
        )

    def read_embedded(self, filepath, *, path=None, audio=None):
        """Read embedded ID3v2 tags and fill missing text from ID3v1, without defaults."""
        if path is None or audio is None:
            path, audio = self._open_audio(filepath)
        tags = audio.tags or {}
        v1 = self._read_id3v1(path)
        return TrackMetadata(
            title=self._text(tags, "TIT2", "title") or v1.get("title") or "",
            artist=self._text(tags, "TPE1", "artist") or v1.get("artist") or "",
            album=self._text(tags, "TALB", "album") or v1.get("album"),
            genre=self._text(tags, "TCON", "genre"),
            bpm=self._number(self._text(tags, "TBPM", "bpm")),
            key=self._text(tags, "TKEY", "initialkey", "key"),
            duration=None,
            bitrate=None,
            sample_rate=None,
        )

    @staticmethod
    def _read_id3v1(path):
        try:
            with path.open("rb") as stream:
                stream.seek(0, 2)
                if stream.tell() < 128:
                    return {}
                stream.seek(-128, 2)
                block = stream.read(128)
        except OSError:
            return {}
        if len(block) != 128 or block[:3] != b"TAG":
            return {}

        def decode(start, end):
            return block[start:end].rstrip(b"\x00 ").decode("latin-1", errors="replace").strip() or None

        return {"title": decode(3, 33), "artist": decode(33, 63), "album": decode(63, 93)}

    @staticmethod
    def _open_audio(filepath):
        path = Path(filepath)
        if not path.is_file():
            raise MetadataReadError("El archivo de audio no existe o no es accesible.")
        try:
            audio = File(path)
        except Exception as error:
            raise MetadataReadError("No se pudo leer la metadata del archivo.") from error
        if audio is None:
            raise MetadataReadError("El archivo no contiene audio compatible.")
        return path, audio

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
