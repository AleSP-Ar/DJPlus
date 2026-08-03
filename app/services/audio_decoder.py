"""Bounded, read-only PCM decoding for local WAV and AIFF files."""

from __future__ import annotations

import aifc
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol, runtime_checkable
import wave


OFFICIAL_AUDIO_FORMAT_ORDER = ("mp3", "flac", "aiff", "wav")


class AudioDecoderError(ValueError):
    """Base error for safe local decoder contracts."""


class UnsupportedAudioFormatError(AudioDecoderError):
    """Raised when no registered decoder supports a file."""


class CorruptAudioFileError(AudioDecoderError):
    """Raised when an expected PCM container cannot be decoded safely."""


@dataclass(frozen=True)
class AudioFormatDTO:
    name: str
    extensions: tuple[str, ...]
    container: str

    def __post_init__(self):
        if self.name not in {*OFFICIAL_AUDIO_FORMAT_ORDER, "ffmpeg"}:
            raise AudioDecoderError("El nombre de formato no esta soportado.")
        if not isinstance(self.extensions, tuple) or not self.extensions or any(
            not isinstance(item, str) or not item.startswith(".") for item in self.extensions
        ):
            raise AudioDecoderError("Las extensiones de formato no son validas.")
        if not isinstance(self.container, str) or not self.container.strip():
            raise AudioDecoderError("El contenedor de audio es obligatorio.")


@dataclass(frozen=True)
class DecodedAudioInfoDTO:
    filepath: str
    audio_format: AudioFormatDTO
    sample_rate: int
    channels: int
    sample_width: int
    frame_count: int

    def __post_init__(self):
        if not isinstance(self.filepath, str) or not self.filepath.strip():
            raise AudioDecoderError("La ruta decodificada es obligatoria.")
        if not isinstance(self.audio_format, AudioFormatDTO):
            raise AudioDecoderError("La informacion requiere un formato de audio.")
        if not isinstance(self.sample_rate, int) or self.sample_rate < 1:
            raise AudioDecoderError("El sample rate debe ser positivo.")
        if not isinstance(self.channels, int) or self.channels not in {1, 2}:
            raise AudioDecoderError("Solo se admiten uno o dos canales PCM.")
        if not isinstance(self.sample_width, int) or self.sample_width not in {1, 2, 3, 4}:
            raise AudioDecoderError("El ancho PCM debe estar entre 8 y 32 bits.")
        if not isinstance(self.frame_count, int) or self.frame_count < 0:
            raise AudioDecoderError("La cantidad de frames no es valida.")

    @property
    def duration_seconds(self):
        return self.frame_count / self.sample_rate


@dataclass(frozen=True)
class AudioPCMBlockDTO:
    info: DecodedAudioInfoDTO
    frame_offset: int
    frame_count: int
    samples: tuple[float, ...]

    def __post_init__(self):
        if not isinstance(self.info, DecodedAudioInfoDTO):
            raise AudioDecoderError("El bloque requiere informacion decodificada.")
        if not isinstance(self.frame_offset, int) or self.frame_offset < 0:
            raise AudioDecoderError("El offset de bloque no es valido.")
        if not isinstance(self.frame_count, int) or self.frame_count < 0:
            raise AudioDecoderError("La cantidad de frames del bloque no es valida.")
        if not isinstance(self.samples, tuple) or len(self.samples) != self.frame_count * self.info.channels:
            raise AudioDecoderError("Las muestras del bloque no coinciden con sus frames.")
        if any(not isinstance(value, (int, float)) or not -1 <= value <= 1 for value in self.samples):
            raise AudioDecoderError("Las muestras PCM deben estar normalizadas entre -1 y 1.")


@runtime_checkable
class AudioDecoderProtocol(Protocol):
    audio_format: AudioFormatDTO

    def can_decode(self, filepath: str, header: bytes) -> bool:
        ...

    def probe(self, filepath: str) -> DecodedAudioInfoDTO:
        ...

    def iter_blocks(self, filepath: str, block_frames: int, cancellation_token=None) -> Iterator[AudioPCMBlockDTO]:
        ...


class _PCMDecoder:
    """Shared standard-library container adapter; it never loads an entire file."""

    audio_format: AudioFormatDTO
    _byteorder = "little"
    _unsigned_8_bit = False

    def can_decode(self, filepath, header):
        return Path(filepath).suffix.casefold() in self.audio_format.extensions

    def _open(self, filepath):
        raise NotImplementedError

    def _validate_container(self, source):
        if source.getcomptype() not in {"NONE", b"NONE"}:
            raise UnsupportedAudioFormatError("Solo se admite PCM sin compresion.")

    def probe(self, filepath):
        path = Path(filepath)
        if not path.is_file():
            raise CorruptAudioFileError("El archivo de audio no existe o no es accesible.")
        try:
            with self._open(str(path)) as source:
                self._validate_container(source)
                return DecodedAudioInfoDTO(
                    str(path), self.audio_format, source.getframerate(), source.getnchannels(),
                    source.getsampwidth(), source.getnframes(),
                )
        except AudioDecoderError:
            raise
        except (aifc.Error, wave.Error, OSError, EOFError) as error:
            raise CorruptAudioFileError("El contenedor PCM esta corrupto o no puede leerse.") from error

    def iter_blocks(self, filepath, block_frames, cancellation_token=None):
        if not isinstance(block_frames, int) or block_frames < 1:
            raise AudioDecoderError("block_frames debe ser positivo.")
        info = self.probe(filepath)
        try:
            with self._open(info.filepath) as source:
                self._validate_container(source)
                offset = 0
                while True:
                    if cancellation_token is not None and cancellation_token.is_cancelled():
                        return
                    raw = source.readframes(block_frames)
                    if not raw:
                        return
                    frame_count = len(raw) // (info.sample_width * info.channels)
                    raw = raw[:frame_count * info.sample_width * info.channels]
                    samples = self._normalise(raw, info.sample_width)
                    yield AudioPCMBlockDTO(info, offset, frame_count, samples)
                    offset += frame_count
        except AudioDecoderError:
            raise
        except (aifc.Error, wave.Error, OSError, EOFError) as error:
            raise CorruptAudioFileError("El contenedor PCM esta corrupto o no puede leerse.") from error

    def _normalise(self, raw, width):
        if width == 1 and self._unsigned_8_bit:
            return tuple((value - 128) / 128 for value in raw)
        maximum = float((1 << (width * 8 - 1)) - 1)
        values = (
            int.from_bytes(raw[index:index + width], self._byteorder, signed=True)
            for index in range(0, len(raw), width)
        )
        return tuple(max(-1.0, min(1.0, value / maximum)) for value in values)


class WAVPCMDecoder(_PCMDecoder):
    audio_format = AudioFormatDTO("wav", (".wav",), "RIFF/WAVE")
    _byteorder = "little"
    _unsigned_8_bit = True

    def can_decode(self, filepath, header):
        return header[:4] == b"RIFF" and header[8:12] == b"WAVE" or super().can_decode(filepath, header)

    def _open(self, filepath):
        return wave.open(filepath, "rb")


class AIFFPCMDecoder(_PCMDecoder):
    audio_format = AudioFormatDTO("aiff", (".aif", ".aiff"), "FORM/AIFF")
    _byteorder = "big"

    def can_decode(self, filepath, header):
        return header[:4] == b"FORM" and header[8:12] in {b"AIFF", b"AIFC"} or super().can_decode(filepath, header)

    def _open(self, filepath):
        return aifc.open(filepath, "rb")


class AudioDecoderRegistry:
    """Select a local decoder from content first and extension second."""

    def __init__(self, decoders=()):
        self._decoders = {}
        for decoder in decoders:
            self.register(decoder)

    @classmethod
    def default(cls, ffmpeg_decoder=None):
        decoders = []
        if ffmpeg_decoder is not None:
            decoders.append(ffmpeg_decoder)
        decoders.extend((AIFFPCMDecoder(), WAVPCMDecoder()))
        return cls(tuple(decoders))

    def register(self, decoder):
        if not isinstance(decoder, AudioDecoderProtocol):
            raise TypeError("AudioDecoderRegistry requiere AudioDecoderProtocol.")
        name = decoder.audio_format.name
        if name in self._decoders:
            raise AudioDecoderError("No se permiten decodificadores duplicados.")
        self._decoders[name] = decoder

    def detect(self, filepath):
        if not isinstance(filepath, str) or not filepath.strip():
            raise AudioDecoderError("La ruta de audio es obligatoria.")
        path = Path(filepath)
        try:
            with path.open("rb") as source:
                header = source.read(12)
        except OSError as error:
            raise CorruptAudioFileError("El archivo de audio no existe o no es accesible.") from error
        content_matches = [decoder for decoder in self._decoders.values() if self._matches_content(decoder, header)]
        if len(content_matches) == 1:
            return content_matches[0]
        extension_matches = [decoder for decoder in self._decoders.values() if path.suffix.casefold() in decoder.audio_format.extensions]
        if len(extension_matches) == 1:
            return extension_matches[0]
        raise UnsupportedAudioFormatError("El formato de audio no es compatible con los decodificadores registrados.")

    def decode(self, filepath, block_frames, cancellation_token=None):
        decoder = self.detect(filepath)
        info = decoder.probe(filepath)
        return info, decoder.iter_blocks(filepath, block_frames, cancellation_token)

    def registered_decoder_names(self):
        """Expose immutable registry diagnostics without decoder implementations."""
        return tuple(self._decoders)

    def optional_decoder(self, name):
        if not isinstance(name, str):
            raise TypeError("El nombre de decoder debe ser texto.")
        return self._decoders.get(name)

    def supported_extensions(self):
        by_format = {
            "mp3": (".mp3",), "flac": (".flac",),
            "aiff": (".aif", ".aiff"), "wav": (".wav",),
        }
        registered = set(self._decoders)
        formats = tuple(
            item for item in OFFICIAL_AUDIO_FORMAT_ORDER
            if item in registered or (item in {"mp3", "flac"} and "ffmpeg" in registered)
        )
        return tuple(extension for item in formats for extension in by_format[item])

    def supported_format_names(self):
        registered = set(self._decoders)
        return tuple(
            item for item in OFFICIAL_AUDIO_FORMAT_ORDER
            if item in registered or (item in {"mp3", "flac"} and "ffmpeg" in registered)
        )

    @staticmethod
    def _matches_content(decoder, header):
        custom = getattr(decoder, "matches_content", None)
        if callable(custom):
            return bool(custom(header))
        if decoder.audio_format.name == "wav":
            return header[:4] == b"RIFF" and header[8:12] == b"WAVE"
        if decoder.audio_format.name == "aiff":
            return header[:4] == b"FORM" and header[8:12] in {b"AIFF", b"AIFC"}
        return False
