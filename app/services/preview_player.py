"""Local preview-player core, isolated from widgets and concrete Qt objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import logging
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

try:  # QtMultimedia is optional at runtime, even when PySide6 UI is installed.
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
    _QT_MULTIMEDIA_IMPORT_ERROR = None
except ImportError as error:  # pragma: no cover - exercised through injected availability.
    QUrl = QAudioOutput = QMediaDevices = QMediaPlayer = None
    _QT_MULTIMEDIA_IMPORT_ERROR = error


OFFICIAL_PREVIEW_FORMAT_ORDER = ("mp3", "flac", "aiff", "wav")
_SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".aif", ".aiff", ".wav"}


class PreviewPlayerError(RuntimeError):
    """Base controlled preview player error."""


class PlaybackBackendUnavailableError(PreviewPlayerError):
    """Raised when Qt multimedia cannot be composed locally."""


class TrackNotLoadedError(PreviewPlayerError):
    """Raised for an operation that needs a loaded track."""


class TrackFileNotFoundError(PreviewPlayerError):
    """Raised when a selected local track does not exist as a file."""


class UnsupportedAudioFormatError(PreviewPlayerError):
    """Raised for an unsupported preview extension."""


class PlaybackLoadError(PreviewPlayerError):
    """Raised when a backend cannot prepare valid media."""


class PlaybackOperationError(PreviewPlayerError):
    """Raised for an invalid playback operation or media capability."""


class PlaybackClosedError(PreviewPlayerError):
    """Raised when an operation arrives after close()."""


class PreviewPlayerState(str, Enum):
    EMPTY = "EMPTY"
    LOADING = "LOADING"
    READY = "READY"
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ENDED = "ENDED"
    ERROR = "ERROR"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class AudioOutputDeviceDTO:
    device_id: str
    description: str
    is_default: bool
    is_available: bool
    backend_name: str

    def __post_init__(self):
        if not isinstance(self.device_id, str) or not self.device_id:
            raise ValueError("device_id es obligatorio y serializable.")
        if not isinstance(self.description, str): raise ValueError("description debe ser texto.")


@dataclass(frozen=True)
class PreviewTrackDTO:
    filepath: str
    track_id: int | None = None
    title: str | None = None
    artist: str | None = None
    duration_ms: int | None = None
    artwork_data: bytes | None = None

    def __post_init__(self):
        if not isinstance(self.filepath, str) or not self.filepath.strip():
            raise ValueError("filepath es obligatoria.")
        if self.track_id is not None and (not isinstance(self.track_id, int) or isinstance(self.track_id, bool) or self.track_id < 0):
            raise ValueError("track_id debe ser entero no negativo o nulo.")
        if self.duration_ms is not None and (not isinstance(self.duration_ms, int) or isinstance(self.duration_ms, bool) or self.duration_ms < 0):
            raise ValueError("duration_ms debe ser entero no negativo o nulo.")
        if self.artwork_data is not None and not isinstance(self.artwork_data, bytes):
            raise ValueError("artwork_data debe ser bytes o nulo.")


@dataclass(frozen=True)
class PreviewPlayerSnapshotDTO:
    state: PreviewPlayerState
    track: PreviewTrackDTO | None
    position_ms: int
    duration_ms: int
    volume: float
    seekable: bool
    error: str | None
    backend_name: str
    output_device_id: str | None = None
    output_device_description: str | None = None
    using_default_device: bool = True
    output_available: bool = True
    degraded_reason: str | None = None


@dataclass(frozen=True)
class PreviewPlayerCapabilitiesDTO:
    formats: tuple[str, ...]
    seek_available: bool
    volume_available: bool
    backend_available: bool
    backend_name: str
    backend_version: str | None = None


PlaybackCallback = Callable[[str, PreviewPlayerSnapshotDTO], None]
BackendCallback = Callable[[str, dict], None]


@runtime_checkable
class AudioPlaybackBackendProtocol(Protocol):
    """Backend contract; QMediaPlayer never crosses this boundary."""

    name: str
    available: bool
    seekable: bool

    def set_event_callback(self, callback: BackendCallback | None) -> None: ...
    def load(self, filepath: str) -> None: ...
    def play(self) -> None: ...
    def pause(self) -> None: ...
    def stop(self) -> None: ...
    def seek(self, position_ms: int) -> None: ...
    def set_volume(self, value: float) -> None: ...
    def get_position(self) -> int: ...
    def get_duration(self) -> int: ...
    def get_error(self) -> str | None: ...
    def close(self) -> None: ...
    def list_output_devices(self) -> tuple[AudioOutputDeviceDTO, ...]: ...
    def get_current_output_device(self) -> AudioOutputDeviceDTO | None: ...
    def set_output_device(self, device_id: str) -> AudioOutputDeviceDTO: ...
    def use_default_output_device(self) -> AudioOutputDeviceDTO | None: ...


@runtime_checkable
class PlaybackHistoryPortProtocol(Protocol):
    def record_played(self, track_id: int) -> None: ...


class HistoryPlaybackPortAdapter:
    """Small adapter over the existing HistoryService; no persistence duplication."""

    def __init__(self, history_service): self._history_service = history_service
    def record_played(self, track_id): self._history_service.record_track_played(track_id)


class DeterministicPlaybackBackend:
    """No-audio backend used by service tests and headless integrations."""

    name = "deterministic"

    def __init__(self, *, available=True, duration_ms=3000, seekable=True, fail_load=False, devices=None, current_device_id=None):
        self.available, self.seekable = available, seekable
        self._duration, self._position, self._volume = duration_ms, 0, 0.8
        self._callback, self._closed, self._error, self._fail_load = None, False, None, fail_load
        default_devices = (AudioOutputDeviceDTO("default", "Deterministic default output", True, bool(available), self.name),)
        self._devices = tuple(devices) if devices is not None else default_devices
        self._current_device_id = current_device_id
        if self._current_device_id is None:
            default = next((device for device in self._devices if device.is_default and device.is_available), None)
            self._current_device_id = default.device_id if default is not None else None

    def set_event_callback(self, callback): self._callback = callback
    def load(self, _filepath):
        self._check_available()
        if self._fail_load:
            self.emit_error("load_failed"); return
        self._position = 0; self._emit("loaded", {"duration_ms": self._duration, "seekable": self.seekable})
    def play(self): self._check_available(); self._emit("state", {"state": "playing"})
    def pause(self): self._check_available(); self._emit("state", {"state": "paused"})
    def stop(self):
        if not self._closed: self._position = 0; self._emit("state", {"state": "stopped"})
    def seek(self, position_ms):
        self._check_available()
        if not self.seekable: raise PlaybackOperationError("El medio no permite seek.")
        self._position = position_ms; self._emit("position", {"position_ms": position_ms})
    def set_volume(self, value): self._check_available(); self._volume = value; self._emit("volume", {"volume": value})
    def get_position(self): return self._position
    def get_duration(self): return self._duration
    def get_error(self): return self._error
    def list_output_devices(self): return tuple(self._devices)
    def get_current_output_device(self):
        return next((device for device in self._devices if device.device_id == self._current_device_id), None)
    def set_output_device(self, device_id):
        self._check_available()
        device = next((item for item in self._devices if item.device_id == device_id and item.is_available), None)
        if device is None: raise PlaybackOperationError("El dispositivo de salida no esta disponible.")
        self._current_device_id = device.device_id
        self._emit("output_device", {"device_id": device.device_id})
        return device
    def use_default_output_device(self):
        self._check_available()
        device = next((item for item in self._devices if item.is_default and item.is_available), None)
        self._current_device_id = device.device_id if device is not None else None
        self._emit("output_device", {"device_id": self._current_device_id})
        return device
    def finish(self): self._position = self._duration; self._emit("ended", {})
    def emit_error(self, error="backend_error"):
        self._error = error; self._emit("error", {"error": error})
    def close(self): self._closed = True; self._callback = None
    def _check_available(self):
        if self._closed: raise PlaybackClosedError("El backend esta cerrado.")
        if not self.available: raise PlaybackBackendUnavailableError("El backend de reproduccion no esta disponible.")
    def _emit(self, event, payload):
        if self._callback is not None and not self._closed: self._callback(event, payload)


class QtMultimediaPlaybackBackend:
    """Thin Qt adapter with safe signal ownership and no auto-play behaviour."""

    name = "qt_multimedia"

    def __init__(self, media_player_factory=None, audio_output_factory=None, *, qt_available=None):
        available = _QT_MULTIMEDIA_IMPORT_ERROR is None if qt_available is None else bool(qt_available)
        if not available:
            raise PlaybackBackendUnavailableError("PySide6.QtMultimedia no esta disponible.")
        try:
            self._player = (media_player_factory or QMediaPlayer)()
            self._audio = (audio_output_factory or QAudioOutput)()
            self._player.setAudioOutput(self._audio)
        except Exception as error:
            raise PlaybackBackendUnavailableError("No se pudo crear el backend multimedia Qt.") from error
        self.available, self.seekable, self._closed, self._callback, self._error = True, True, False, None, None
        self._volume = 0.8
        self._connections = ()
        self._connect_signals()

    def set_event_callback(self, callback): self._callback = callback
    def load(self, filepath): self._ensure_open(); self._player.setSource(QUrl.fromLocalFile(filepath))
    def play(self): self._ensure_open(); self._player.play()
    def pause(self): self._ensure_open(); self._player.pause()
    def stop(self):
        if not self._closed: self._player.stop()
    def seek(self, position_ms): self._ensure_open(); self._player.setPosition(position_ms)
    def set_volume(self, value): self._ensure_open(); self._volume = float(value); self._audio.setVolume(self._volume)
    def get_position(self): return 0 if self._closed else int(self._player.position())
    def get_duration(self): return 0 if self._closed else max(0, int(self._player.duration()))
    def get_error(self): return self._error
    @staticmethod
    def _device_id(device):
        try:
            raw = bytes(device.id())
        except Exception:
            raw = b""
        return raw.hex() or "default-audio-output"
    def _device_dto(self, device, default_id=None):
        identifier = self._device_id(device)
        return AudioOutputDeviceDTO(identifier, str(device.description()), identifier == default_id, True, self.name)
    def list_output_devices(self):
        self._ensure_open()
        devices = tuple(QMediaDevices.audioOutputs())
        default_id = self._device_id(QMediaDevices.defaultAudioOutput())
        return tuple(self._device_dto(device, default_id) for device in devices)
    def get_current_output_device(self):
        self._ensure_open()
        current_id = self._device_id(self._audio.device())
        return next((device for device in self.list_output_devices() if device.device_id == current_id), None)
    def set_output_device(self, device_id):
        self._ensure_open()
        raw_devices = tuple(QMediaDevices.audioOutputs())
        default_id = self._device_id(QMediaDevices.defaultAudioOutput())
        for device in raw_devices:
            if self._device_id(device) == device_id:
                self._audio.setDevice(device)
                self._audio.setVolume(self._volume)
                return self._device_dto(device, default_id)
        raise PlaybackOperationError("El dispositivo de salida no esta disponible.")
    def use_default_output_device(self):
        self._ensure_open()
        device = QMediaDevices.defaultAudioOutput()
        default_id = self._device_id(device)
        if not any(self._device_id(item) == default_id for item in tuple(QMediaDevices.audioOutputs())):
            return None
        self._audio.setDevice(device)
        self._audio.setVolume(self._volume)
        return self._device_dto(device, default_id)

    def close(self):
        if self._closed: return
        self._closed = True
        try: self._player.stop()
        except RuntimeError: pass
        for signal, slot in self._connections:
            try: signal.disconnect(slot)
            except (RuntimeError, TypeError): pass
        self._connections, self._callback = (), None
        for value in (self._player, self._audio):
            try: value.deleteLater()
            except RuntimeError: pass

    def _connect_signals(self):
        connections = (
            (self._player.positionChanged, self._on_position), (self._player.durationChanged, self._on_duration),
            (self._player.playbackStateChanged, self._on_state), (self._player.mediaStatusChanged, self._on_media_status),
            (self._player.errorOccurred, self._on_error),
        )
        for signal, slot in connections: signal.connect(slot)
        self._connections = connections

    def _on_position(self, value): self._emit("position", {"position_ms": max(0, int(value))})
    def _on_duration(self, value): self._emit("duration", {"duration_ms": max(0, int(value))})
    def _on_state(self, value):
        mapping = {QMediaPlayer.PlaybackState.PlayingState: "playing", QMediaPlayer.PlaybackState.PausedState: "paused", QMediaPlayer.PlaybackState.StoppedState: "stopped"}
        self._emit("state", {"state": mapping.get(value, "stopped")})
    def _on_media_status(self, value):
        if value == QMediaPlayer.MediaStatus.LoadedMedia: self._emit("loaded", {"duration_ms": self.get_duration(), "seekable": True})
        elif value == QMediaPlayer.MediaStatus.EndOfMedia: self._emit("ended", {})
        elif value == QMediaPlayer.MediaStatus.InvalidMedia: self._on_error()
    def _on_error(self, *_args):
        self._error = "qt_multimedia_error"; self._emit("error", {"error": self._error})
    def _emit(self, event, payload):
        if not self._closed and self._callback is not None: self._callback(event, payload)
    def _ensure_open(self):
        if self._closed: raise PlaybackClosedError("El backend multimedia esta cerrado.")


class PreviewPlayerService:
    """Stateful, UI-free preview-player facade over an injected backend."""

    def __init__(self, backend, *, initial_volume=0.70, logger=None, settings_service=None, history_port=None):
        if not isinstance(backend, AudioPlaybackBackendProtocol):
            raise TypeError("PreviewPlayerService requiere AudioPlaybackBackendProtocol.")
        self._backend, self._logger = backend, logger or logging.getLogger("djplus.preview")
        self._settings_service, self._history_port = settings_service, history_port
        self._callbacks, self._closed = [], False
        self._track, self._position, self._duration, self._seekable, self._error = None, 0, 0, False, None
        self._state, self._played_for_load = PreviewPlayerState.EMPTY, False
        self._output_device, self._degraded_reason = None, None
        self._volume = self._validate_volume(initial_volume)
        self._backend.set_event_callback(self._on_backend_event)
        if not backend.available:
            self._state, self._error, self._degraded_reason = PreviewPlayerState.ERROR, "backend_unavailable", "backend_unavailable"
        else:
            self._backend.set_volume(self._volume)
            self._refresh_output_device()

    def capabilities(self):
        return PreviewPlayerCapabilitiesDTO(OFFICIAL_PREVIEW_FORMAT_ORDER, True, True, bool(self._backend.available), self._backend.name, None)

    def subscribe(self, callback):
        if not callable(callback): raise TypeError("El callback de preview debe ser invocable.")
        self._ensure_open(); self._callbacks.append(callback)
        return lambda: self._unsubscribe(callback)

    def load_track(self, track):
        self._ensure_open()
        if not isinstance(track, PreviewTrackDTO): raise TypeError("load_track requiere PreviewTrackDTO.")
        path = Path(track.filepath).expanduser()
        if not path.exists() or not path.is_file(): raise TrackFileNotFoundError("El archivo de preescucha no existe.")
        if path.suffix.casefold() not in _SUPPORTED_EXTENSIONS: raise UnsupportedAudioFormatError("El formato no esta soportado para preescucha.")
        self._track, self._position, self._duration, self._error, self._played_for_load = track, 0, track.duration_ms or 0, None, False
        self._set_state(PreviewPlayerState.LOADING)
        self._log("preview_track_load_started", track)
        try: self._backend.load(str(path))
        except PreviewPlayerError: raise
        except Exception as error:
            self._set_error(type(error).__name__); raise PlaybackLoadError("No se pudo cargar la pista de preescucha.") from error
        if self._state == PreviewPlayerState.LOADING: self._set_state(PreviewPlayerState.READY)
        return self.snapshot()

    def play(self):
        self._require_track(); self._ensure_open()
        if self._state == PreviewPlayerState.ENDED: self.seek(0)
        self._backend.play(); self._log("preview_playback_started", self._track); return self.snapshot()
    def pause(self):
        self._require_track(); self._ensure_open(); self._backend.pause(); self._set_state(PreviewPlayerState.PAUSED); self._log("preview_playback_paused", self._track); return self.snapshot()
    def toggle_play_pause(self): return self.pause() if self._state == PreviewPlayerState.PLAYING else self.play()
    def stop(self):
        self._require_track(); self._ensure_open(); self._backend.stop(); self._position = 0; self._set_state(PreviewPlayerState.STOPPED); self._log("preview_playback_stopped", self._track); return self.snapshot()

    def seek(self, position_ms):
        self._require_track(); self._ensure_open()
        if not isinstance(position_ms, (int, float)) or isinstance(position_ms, bool): raise PlaybackOperationError("La posicion debe ser numerica.")
        if not self._seekable: raise PlaybackOperationError("El medio no permite seek.")
        position = max(0, int(position_ms)); position = min(position, self._duration) if self._duration else position
        self._backend.seek(position); self._position = position; self._emit("position_changed"); self._log("preview_seek_completed", self._track); return self.snapshot()

    def set_volume(self, value):
        self._ensure_open(); self._volume = self._validate_volume(value); self._backend.set_volume(self._volume); self._emit("volume_changed"); return self.snapshot()
    def unload(self):
        self._ensure_open()
        if self._track is not None: self._backend.stop()
        self._track, self._position, self._duration, self._seekable, self._error, self._played_for_load = None, 0, 0, False, None, False
        self._set_state(PreviewPlayerState.EMPTY); return self.snapshot()
    def snapshot(self):
        device = self._output_device
        return PreviewPlayerSnapshotDTO(self._state, self._track, self._position, self._duration, self._volume, self._seekable, self._error, self._backend.name,
            device.device_id if device else None, device.description if device else None, bool(device and device.is_default), device is not None,
            self._degraded_reason)

    def list_output_devices(self):
        self._ensure_open()
        devices = tuple(self._backend.list_output_devices())
        self._refresh_output_device(devices)
        self._log("preview_output_devices_listed", None, device_count=len(devices))
        return devices

    def current_output_device(self):
        self._ensure_open(); self._refresh_output_device(); return self._output_device

    def select_output_device(self, device_id):
        self._ensure_open()
        if not isinstance(device_id, str) or not device_id.strip(): raise PlaybackOperationError("device_id es obligatorio.")
        self._output_device = self._backend.set_output_device(device_id)
        self._degraded_reason = None
        self._emit("output_device_changed")
        self._log("preview_output_device_selected", None, device_ref=self._device_ref(device_id))
        return self.snapshot()

    def use_default_output_device(self):
        self._ensure_open()
        self._output_device = self._backend.use_default_output_device()
        self._degraded_reason = None if self._output_device else "no_output_device"
        self._emit("output_device_changed")
        self._log("preview_output_device_defaulted", None, output_available=self._output_device is not None)
        return self.snapshot()

    def load_preferences(self):
        """Apply settings explicitly with safe configured-id/description/default fallback."""
        self._ensure_open()
        if self._settings_service is None: return self.snapshot()
        preferences = self._settings_service.get().preview_player
        self.set_volume(preferences.volume)
        if not self._backend.available:
            self._degraded_reason = "backend_unavailable"; return self.snapshot()
        devices = self.list_output_devices()
        selected = next((item for item in devices if item.device_id == preferences.output_device_id and item.is_available), None)
        if selected is None and preferences.output_device_description:
            selected = next((item for item in devices if item.description == preferences.output_device_description and item.is_available), None)
        if selected is not None:
            self.select_output_device(selected.device_id)
        else:
            self.use_default_output_device()
            if preferences.output_device_id or preferences.output_device_description:
                self._log("preview_output_device_fallback", None, fallback="default_or_unavailable")
        self._log("preview_preferences_loaded", None)
        return self.snapshot()

    def save_preferences(self):
        self._ensure_open()
        if self._settings_service is None: raise PlaybackOperationError("No hay SettingsService configurado.")
        device = self.current_output_device()
        self._settings_service.update({"preview_player": {"volume": self._volume,
            "output_device_id": device.device_id if device else None,
            "output_device_description": device.description if device else None}})
        self._log("preview_preferences_saved", None, output_available=device is not None)
        return self.snapshot()

    def close(self):
        if self._closed: return
        try: self._backend.stop()
        except Exception: pass
        self._backend.close(); self._closed, self._state, self._callbacks, self._played_for_load = True, PreviewPlayerState.CLOSED, [], False
        self._log("preview_player_closed", None)

    def _on_backend_event(self, event, payload):
        if self._closed: return
        if event == "loaded":
            self._duration = max(0, int(payload.get("duration_ms", self._duration)))
            self._seekable = bool(payload.get("seekable", True)); self._set_state(PreviewPlayerState.READY); self._emit("track_loaded"); self._log("preview_track_loaded", self._track)
        elif event == "state":
            state = {"playing": PreviewPlayerState.PLAYING, "paused": PreviewPlayerState.PAUSED, "stopped": PreviewPlayerState.STOPPED}.get(payload.get("state"))
            if state is not None:
                self._set_state(state)
                if state == PreviewPlayerState.PLAYING: self._record_played_once()
        elif event == "position": self._position = max(0, int(payload.get("position_ms", 0))); self._emit("position_changed")
        elif event == "duration": self._duration = max(0, int(payload.get("duration_ms", 0))); self._emit("duration_changed")
        elif event == "volume": self._volume = self._validate_volume(payload.get("volume", self._volume)); self._emit("volume_changed")
        elif event == "ended": self._position = self._duration; self._set_state(PreviewPlayerState.ENDED); self._emit("playback_ended"); self._log("preview_playback_ended", self._track)
        elif event == "error": self._set_error(payload.get("error", "backend_error"))

    def _refresh_output_device(self, devices=None):
        try:
            self._output_device = self._backend.get_current_output_device()
            if self._output_device is None: self._degraded_reason = "no_output_device"
            else: self._degraded_reason = None
        except Exception:
            self._output_device, self._degraded_reason = None, "output_device_unavailable"
        return self._output_device
    def _record_played_once(self):
        if self._played_for_load or self._track is None or self._track.track_id is None: return
        self._played_for_load = True
        if self._history_port is None: return
        try:
            self._history_port.record_played(self._track.track_id)
            self._log("preview_history_recorded", self._track)
        except Exception as error:
            self._log("preview_history_failed", self._track, error_type=type(error).__name__)
    @staticmethod
    def _device_ref(device_id): return hashlib.sha256(device_id.encode("utf-8")).hexdigest()[:12]
    def _set_state(self, state):
        if self._state != state: self._state = state; self._emit("state_changed")
    def _set_error(self, code):
        self._error, self._state = "playback_error", PreviewPlayerState.ERROR; self._emit("playback_error"); self._log("preview_playback_failed", self._track, error_code=str(code))
    def _emit(self, event):
        if self._closed: return
        snapshot = self.snapshot()
        for callback in tuple(self._callbacks):
            try: callback(event, snapshot)
            except Exception: self._logger.warning("Preview callback failed", extra={"event_name": "preview_callback_failed", "component": "preview"})
    def _unsubscribe(self, callback):
        if callback in self._callbacks: self._callbacks.remove(callback)
    def _require_track(self):
        if self._track is None: raise TrackNotLoadedError("No hay pista cargada para preescucha.")
    def _ensure_open(self):
        if self._closed: raise PlaybackClosedError("El reproductor de preescucha esta cerrado.")
    @staticmethod
    def _validate_volume(value):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= float(value) <= 1.0: raise PlaybackOperationError("El volumen debe estar entre 0.0 y 1.0.")
        return float(value)
    def _log(self, event, track, **context):
        if track is not None:
            context["track_id"] = track.track_id
            context["format"] = Path(track.filepath).suffix.casefold().lstrip(".")
            context["track_ref"] = hashlib.sha256(track.filepath.encode("utf-8")).hexdigest()[:12]
        self._logger.info("Preview player operation", extra={"event_name": event, "component": "preview", "context": context})


def create_preview_player_service(*, initial_volume=None, logger=None, backend=None, settings_service=None, history_port=None):
    """Canonical local composition point; unavailable multimedia stays degraded, not fatal."""
    if initial_volume is None:
        initial_volume = 0.70
        if settings_service is not None:
            try: initial_volume = settings_service.get().preview_player.volume
            except Exception: pass
    if backend is None:
        try:
            backend = QtMultimediaPlaybackBackend()
        except PlaybackBackendUnavailableError:
            backend = DeterministicPlaybackBackend(available=False, devices=())
    service = PreviewPlayerService(backend, initial_volume=initial_volume, logger=logger, settings_service=settings_service, history_port=history_port)
    if settings_service is not None and backend.available:
        try: service.load_preferences()
        except Exception:
            service._log("preview_preferences_load_failed", None)
    return service
