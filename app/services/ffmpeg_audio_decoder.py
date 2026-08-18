"""Optional, bounded FFmpeg decoder for MP3 and FLAC without temporary files."""

from __future__ import annotations

from dataclasses import dataclass
from io import BufferedReader
from pathlib import Path
from queue import Empty, Full, Queue
import hashlib
import logging
import os
import re
import shutil
import subprocess
from threading import Event, Thread
import time

from .audio_decoder import (
    AudioDecoderError,
    AudioFormatDTO,
    AudioPCMBlockDTO,
    DecodedAudioInfoDTO,
)

_LOGGER = logging.getLogger("djplus.ffmpeg")


class FFmpegProcessError(AudioDecoderError):
    """Raised for unavailable, timed-out or failed FFmpeg processes."""

    def __init__(self, message, safe_stderr=""):
        self.safe_stderr = safe_stderr
        super().__init__(message + (f": {safe_stderr}" if safe_stderr else ""))


class FFmpegRuntimeIntegrityError(AudioDecoderError):
    """Raised when the bundled runtime checksum cannot be verified."""


@dataclass(frozen=True)
class FFmpegResolutionDTO:
    executable: str | None
    origin: str
    error: str | None = None
    checksum_verified: bool | None = None

    def __post_init__(self):
        if self.origin not in {"configured", "path", "bundled", "unavailable"}:
            raise AudioDecoderError("El origen de FFmpeg no es valido.")
        if self.executable is not None and (not isinstance(self.executable, str) or not self.executable.strip()):
            raise AudioDecoderError("El ejecutable resuelto no es valido.")
        if (self.executable is None) != (self.origin == "unavailable"):
            raise AudioDecoderError("El origen debe coincidir con el ejecutable resuelto.")
        if self.error is not None and (not isinstance(self.error, str) or not self.error.strip()):
            raise AudioDecoderError("El error de resolucion no es valido.")
        if self.checksum_verified is not None and not isinstance(self.checksum_verified, bool):
            raise AudioDecoderError("El estado de checksum de FFmpeg no es valido.")
        if self.origin == "bundled" and self.checksum_verified is not True:
            raise AudioDecoderError("El runtime incluido requiere checksum verificado.")
        if self.origin != "bundled" and self.checksum_verified is not None:
            raise AudioDecoderError("Solo el runtime incluido puede informar checksum.")


@dataclass(frozen=True)
class FFmpegCapabilityDTO:
    resolution: FFmpegResolutionDTO
    available: bool
    version: str | None
    supports_mp3: bool
    supports_flac: bool
    error: str | None = None

    def __post_init__(self):
        if not isinstance(self.resolution, FFmpegResolutionDTO) or not isinstance(self.available, bool):
            raise AudioDecoderError("La capacidad de FFmpeg no es valida.")
        if self.version is not None and (not isinstance(self.version, str) or not self.version.strip()):
            raise AudioDecoderError("La version de FFmpeg no es valida.")
        if not isinstance(self.supports_mp3, bool) or not isinstance(self.supports_flac, bool):
            raise AudioDecoderError("El soporte de formatos de FFmpeg debe ser booleano.")
        if self.available != (self.resolution.executable is not None and self.error is None):
            raise AudioDecoderError("La disponibilidad no coincide con la resolucion de FFmpeg.")
        if self.error is not None and (not isinstance(self.error, str) or not self.error.strip()):
            raise AudioDecoderError("El error de capacidad no es valido.")


@dataclass(frozen=True)
class FFmpegAvailabilityDTO:
    available: bool
    executable: str | None
    reason: str | None = None
    origin: str = "unavailable"
    version: str | None = None
    supports_mp3: bool = False
    supports_flac: bool = False
    checksum_verified: bool | None = None

    def __post_init__(self):
        if not isinstance(self.available, bool):
            raise AudioDecoderError("La disponibilidad de FFmpeg debe ser booleana.")
        if self.executable is not None and (not isinstance(self.executable, str) or not self.executable.strip()):
            raise AudioDecoderError("El ejecutable de FFmpeg no es valido.")
        if self.available and self.executable is None:
            raise AudioDecoderError("FFmpeg disponible requiere un ejecutable resuelto.")
        if self.reason is not None and (not isinstance(self.reason, str) or not self.reason.strip()):
            raise AudioDecoderError("La razon de disponibilidad no es valida.")
        if self.origin not in {"configured", "path", "bundled", "unavailable"}:
            raise AudioDecoderError("El origen de FFmpeg no es valido.")
        if self.version is not None and (not isinstance(self.version, str) or not self.version.strip()):
            raise AudioDecoderError("La version de FFmpeg no es valida.")
        if not isinstance(self.supports_mp3, bool) or not isinstance(self.supports_flac, bool):
            raise AudioDecoderError("El soporte de FFmpeg debe ser booleano.")
        if self.checksum_verified is not None and not isinstance(self.checksum_verified, bool):
            raise AudioDecoderError("El estado de checksum de FFmpeg no es valido.")


@dataclass(frozen=True)
class FFmpegDecoderConfigDTO:
    executable_path: str | None = None
    timeout_seconds: float = 15.0
    max_stderr_chars: int = 500

    def __post_init__(self):
        if self.executable_path is not None and (not isinstance(self.executable_path, str) or not self.executable_path.strip()):
            raise AudioDecoderError("La ruta configurada de FFmpeg no es valida.")
        if not isinstance(self.timeout_seconds, (int, float)) or not 0.1 <= self.timeout_seconds <= 120:
            raise AudioDecoderError("El timeout de FFmpeg debe estar entre 0.1 y 120 segundos.")
        if not isinstance(self.max_stderr_chars, int) or not 64 <= self.max_stderr_chars <= 4096:
            raise AudioDecoderError("El limite de stderr debe estar entre 64 y 4096 caracteres.")


class FFmpegResolver:
    """Resolve a local executable without changing PATH or installing anything."""

    def __init__(self, config=None, which=None, path_exists=None, bundled_path=None, checksum_path=None, allow_path=True, allow_bundled=True):
        self._config = config or FFmpegDecoderConfigDTO()
        if not isinstance(self._config, FFmpegDecoderConfigDTO):
            raise TypeError("FFmpegResolver requiere FFmpegDecoderConfigDTO.")
        self._which = which or shutil.which
        self._path_exists = path_exists or (lambda value: Path(value).is_file())
        self._bundled_path = bundled_path or str(Path(__file__).resolve().parents[2] / "runtime" / "ffmpeg" / "ffmpeg.exe")
        self._checksum_path = checksum_path or str(Path(self._bundled_path).with_name("CHECKSUM.sha256"))
        if not isinstance(allow_path, bool) or not isinstance(allow_bundled, bool):
            raise TypeError("allow_path y allow_bundled deben ser booleanos.")
        self._allow_path, self._allow_bundled = allow_path, allow_bundled

    def resolve(self):
        configured_error = None
        if self._config.executable_path is not None:
            if self._path_exists(self._config.executable_path):
                return self._record_resolution(FFmpegResolutionDTO(self._config.executable_path, "configured"))
            configured_error = "La ruta configurada de FFmpeg no es ejecutable."
        path_executable = self._which("ffmpeg") if self._allow_path else None
        if path_executable and self._path_exists(path_executable):
            return self._record_resolution(FFmpegResolutionDTO(path_executable, "path"))
        bundled_error = None
        if self._allow_bundled and self._path_exists(self._bundled_path):
            try:
                self._verify_bundled_checksum()
            except FFmpegRuntimeIntegrityError as error:
                bundled_error = str(error)
            else:
                return self._record_resolution(FFmpegResolutionDTO(self._bundled_path, "bundled", checksum_verified=True))
        return self._record_resolution(FFmpegResolutionDTO(
            None,
            "unavailable",
            configured_error or bundled_error or "FFmpeg no esta disponible en configuracion, PATH ni runtime incluido.",
        ))

    @staticmethod
    def _record_resolution(resolution):
        _LOGGER.info("FFmpeg resolution completed", extra={"event_name": "ffmpeg_resolution", "component": "ffmpeg", "context": {"origin": resolution.origin, "available": resolution.executable is not None, "checksum_verified": resolution.checksum_verified}})
        return resolution

    def _verify_bundled_checksum(self):
        checksum_file = Path(self._checksum_path)
        executable = Path(self._bundled_path)
        if not checksum_file.is_file():
            raise FFmpegRuntimeIntegrityError("Falta CHECKSUM.sha256 para el runtime FFmpeg incluido")
        expected = None
        try:
            for line in checksum_file.read_text(encoding="utf-8").splitlines():
                fields = line.strip().split()
                if len(fields) >= 2 and Path(fields[-1].lstrip("*")).name.casefold() == executable.name.casefold():
                    expected = fields[0].casefold()
                    break
        except OSError as error:
            raise FFmpegRuntimeIntegrityError("No se pudo leer CHECKSUM.sha256 del runtime FFmpeg") from error
        if expected is None or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise FFmpegRuntimeIntegrityError("CHECKSUM.sha256 no contiene un hash valido para ffmpeg.exe")
        digest = hashlib.sha256()
        try:
            with executable.open("rb") as binary:
                for block in iter(lambda: binary.read(1024 * 1024), b""):
                    digest.update(block)
        except OSError as error:
            raise FFmpegRuntimeIntegrityError("No se pudo verificar ffmpeg.exe incluido") from error
        if digest.hexdigest().casefold() != expected:
            raise FFmpegRuntimeIntegrityError("Checksum invalido para el runtime FFmpeg incluido")


class FFmpegCapabilityProbe:
    """Use FFmpeg locally to verify executable version and decoder support."""

    def __init__(self, config=None, process_factory=None):
        self._config = config or FFmpegDecoderConfigDTO()
        if not isinstance(self._config, FFmpegDecoderConfigDTO):
            raise TypeError("FFmpegCapabilityProbe requiere FFmpegDecoderConfigDTO.")
        self._process_factory = process_factory or subprocess.Popen

    def probe(self, resolution):
        if not isinstance(resolution, FFmpegResolutionDTO):
            raise TypeError("FFmpegCapabilityProbe.probe requiere FFmpegResolutionDTO.")
        if resolution.executable is None:
            return FFmpegCapabilityDTO(resolution, False, None, False, False, resolution.error)
        try:
            version_output = self._run([resolution.executable, "-hide_banner", "-version"])
            decoders_output = self._run([resolution.executable, "-hide_banner", "-decoders"])
        except FFmpegProcessError as error:
            return FFmpegCapabilityDTO(resolution, False, None, False, False, str(error))
        version_match = re.search(r"ffmpeg version\s+([^\s]+)", version_output, re.IGNORECASE)
        return FFmpegCapabilityDTO(
            resolution, True, version_match.group(1) if version_match else "unknown",
            bool(re.search(r"\bmp3\b", decoders_output, re.IGNORECASE)),
            bool(re.search(r"\bflac\b", decoders_output, re.IGNORECASE)),
        )

    def _run(self, command):
        try:
            process = self._process_factory(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(timeout=self._config.timeout_seconds)
        except subprocess.TimeoutExpired as error:
            try:
                process.terminate(); process.wait(timeout=1)
            except Exception:
                pass
            raise FFmpegProcessError("FFmpeg excedio el timeout de capability probe") from error
        except (OSError, ValueError) as error:
            raise FFmpegProcessError("No se pudo iniciar FFmpeg para capability probe") from error
        if process.returncode not in {0, None}:
            raise FFmpegProcessError("FFmpeg fallo durante capability probe")
        return (stdout or b"").decode("utf-8", "replace") + "\n" + (stderr or b"").decode("utf-8", "replace")


class FFmpegAudioDecoder:
    """Decode MP3/FLAC to signed-16 little-endian PCM over stdout only."""

    audio_format = AudioFormatDTO("ffmpeg", (".mp3", ".flac"), "FFmpeg stdin/stdout")
    _MP3 = AudioFormatDTO("mp3", (".mp3",), "MPEG Audio")
    _FLAC = AudioFormatDTO("flac", (".flac",), "FLAC")

    def __init__(self, config=None, process_factory=None, which=None, path_exists=None, resolver=None, capability_probe=None):
        self._config = config or FFmpegDecoderConfigDTO()
        if not isinstance(self._config, FFmpegDecoderConfigDTO):
            raise TypeError("FFmpegAudioDecoder requiere FFmpegDecoderConfigDTO.")
        self._process_factory = process_factory or subprocess.Popen
        self._which = which or shutil.which
        self._path_exists = path_exists or (lambda value: Path(value).is_file())
        self._resolver = resolver or FFmpegResolver(self._config, self._which, self._path_exists)
        self._capability_probe = capability_probe or FFmpegCapabilityProbe(self._config, self._process_factory)
        if not isinstance(self._resolver, FFmpegResolver):
            raise TypeError("FFmpegAudioDecoder requiere FFmpegResolver.")
        if not isinstance(self._capability_probe, FFmpegCapabilityProbe):
            raise TypeError("FFmpegAudioDecoder requiere FFmpegCapabilityProbe.")
        self._capability_cache = None

    def availability(self):
        capability = self.capabilities()
        return FFmpegAvailabilityDTO(
            capability.available, capability.resolution.executable, capability.error,
            capability.resolution.origin, capability.version, capability.supports_mp3, capability.supports_flac,
            capability.resolution.checksum_verified,
        )

    def capabilities(self, refresh=False):
        if refresh or self._capability_cache is None:
            self._capability_cache = self._capability_probe.probe(self._resolver.resolve())
        return self._capability_cache

    def matches_content(self, header):
        return header[:4] == b"fLaC" or header[:3] == b"ID3" or (
            len(header) > 1 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
        )

    def can_decode(self, filepath, header):
        return self.matches_content(header) or Path(filepath).suffix.casefold() in self.audio_format.extensions

    def probe(self, filepath):
        path = Path(filepath)
        audio_format = self._format_for(path)
        executable = self._require_executable(audio_format.name)
        if not path.is_file():
            raise FFmpegProcessError("El archivo de audio no existe o no es accesible")
        process = self._start(
            [executable, "-hide_banner", "-nostdin", "-i", str(path), "-frames:a", "0", "-f", "null", "-"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            _stdout, stderr = process.communicate(timeout=self._config.timeout_seconds)
        except subprocess.TimeoutExpired as error:
            self._stop_process(process)
            raise FFmpegProcessError("FFmpeg excedio el timeout de sondeo") from error
        raw_stderr = (stderr or b"").decode("utf-8", "replace")
        safe_stderr = self._safe_stderr(raw_stderr, str(path))
        if process.returncode not in {0, None}:
            raise FFmpegProcessError("FFmpeg no pudo inspeccionar el audio", safe_stderr)
        try:
            sample_rate, channels = self._parse_stream(raw_stderr)
        except FFmpegProcessError as error:
            raise FFmpegProcessError("FFmpeg no informo sample rate y canales", safe_stderr) from error
        duration = self._parse_duration(raw_stderr)
        return DecodedAudioInfoDTO(
            str(path), audio_format, sample_rate, channels, 2,
            int(round(duration * sample_rate)) if duration is not None else 0,
        )

    def iter_blocks(self, filepath, block_frames, cancellation_token=None):
        if not isinstance(block_frames, int) or block_frames < 1:
            raise AudioDecoderError("block_frames debe ser positivo.")
        info = self.probe(filepath)
        executable = self._require_executable(info.audio_format.name)
        process = self._start(
            [executable, "-v", "error", "-nostdin", "-i", info.filepath, "-f", "s16le", "-acodec", "pcm_s16le", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if process.stdout is None:
            self._stop_process(process)
            raise FFmpegProcessError("FFmpeg no expuso stdout PCM.")
        started, offset, bytes_per_frame = time.monotonic(), 0, info.channels * 2
        pcm_chunks = self._stdout_blocks(process, block_frames * bytes_per_frame, cancellation_token, started)
        try:
            while True:
                raw = next(pcm_chunks, None)
                if raw is None:
                    if self._cancelled(cancellation_token):
                        return
                    break
                frame_count = len(raw) // bytes_per_frame
                raw = raw[:frame_count * bytes_per_frame]
                samples = tuple(
                    max(-1.0, min(1.0, int.from_bytes(raw[index:index + 2], "little", signed=True) / 32767.0))
                    for index in range(0, len(raw), 2)
                )
                yield AudioPCMBlockDTO(info, offset, frame_count, samples)
                offset += frame_count
            self._wait(process, started)
            stderr = process.stderr.read(self._config.max_stderr_chars * 4 + 1) if process.stderr is not None else b""
            if process.returncode not in {0, None}:
                raise FFmpegProcessError("FFmpeg no pudo decodificar el audio", self._safe_stderr(stderr, info.filepath))
        finally:
            self._close_process_streams(process)

    def _require_executable(self, audio_format=None):
        availability = self.availability()
        if not availability.available:
            raise FFmpegProcessError(availability.reason or "FFmpeg no esta disponible.")
        if audio_format == "mp3" and not availability.supports_mp3:
            raise FFmpegProcessError("FFmpeg no soporta decodificacion MP3.")
        if audio_format == "flac" and not availability.supports_flac:
            raise FFmpegProcessError("FFmpeg no soporta decodificacion FLAC.")
        return availability.executable

    def _start(self, command, **kwargs):
        try:
            return self._process_factory(command, **kwargs)
        except (OSError, ValueError) as error:
            raise FFmpegProcessError("No se pudo iniciar FFmpeg") from error

    def _wait(self, process, started):
        remaining = self._config.timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            self._stop_process(process)
            raise FFmpegProcessError("FFmpeg excedio el timeout de decodificacion")
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as error:
            self._stop_process(process)
            raise FFmpegProcessError("FFmpeg excedio el timeout de decodificacion") from error

    def _stdout_blocks(self, process, chunk_size, cancellation_token, started):
        """Read one bounded PCM chunk at a time without blocking timeout control."""
        queue, stopped, finished = Queue(maxsize=1), Event(), object()

        def put(item):
            while not stopped.is_set():
                try:
                    queue.put(item, timeout=0.05)
                    return True
                except Full:
                    pass
            return False

        def reader():
            try:
                while not stopped.is_set():
                    raw = process.stdout.read(chunk_size)
                    if not put(raw) or not raw:
                        return
            except (OSError, ValueError) as error:
                put(error)
            finally:
                put(finished)

        thread = Thread(target=reader, daemon=True)
        thread.start()
        try:
            while True:
                if self._cancelled(cancellation_token):
                    stopped.set(); self._stop_process(process); return
                remaining = self._config.timeout_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    stopped.set(); self._stop_process(process)
                    raise FFmpegProcessError("FFmpeg excedio el timeout de decodificacion")
                try:
                    item = queue.get(timeout=min(0.1, remaining))
                except Empty:
                    continue
                if item is finished:
                    return
                if isinstance(item, Exception):
                    raise FFmpegProcessError("No se pudo leer stdout PCM de FFmpeg") from item
                if not item:
                    return
                yield item
        finally:
            stopped.set()
            thread.join(timeout=1)

    def _stop_process(self, process):
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
        finally:
            self._close_process_streams(process)

    @staticmethod
    def _close_process_streams(process):
        for stream in (getattr(process, "stdout", None), getattr(process, "stderr", None)):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass

    def _safe_stderr(self, value, filepath):
        text = value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value or "")
        text = text.replace(filepath, "<audio-file>")
        text = re.sub(r"(?i)(token|password|api[_-]?key)\s*[=:]\s*\S+", r"\1=<redacted>", text)
        return " ".join(text.split())[:self._config.max_stderr_chars]

    @staticmethod
    def _parse_stream(stderr):
        match = re.search(r"Audio:.*?(\d+)\s+Hz,\s*(mono|stereo)", stderr, re.IGNORECASE)
        if match is None:
            raise FFmpegProcessError("FFmpeg no informo sample rate y canales", stderr)
        return int(match.group(1)), 1 if match.group(2).casefold() == "mono" else 2

    @staticmethod
    def _parse_duration(stderr):
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr, re.IGNORECASE)
        if match is None:
            return None
        return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))

    def _format_for(self, path):
        return self._FLAC if path.suffix.casefold() == ".flac" else self._MP3

    @staticmethod
    def _cancelled(token):
        return token is not None and token.is_cancelled()
