"""Local structured JSONL logging, diagnostics export and explicit exception hooks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import sys
import tempfile
from threading import RLock, current_thread, local
import traceback

from app.version import VERSION
from .settings_service import LoggingSettingsDTO


class AppLoggingError(RuntimeError):
    """Base logging and diagnostics failure."""


class LoggingConfigurationError(AppLoggingError):
    """Raised when the local structured handler cannot be configured."""


class DiagnosticsExportError(AppLoggingError):
    """Raised when a bounded support export cannot be written safely."""


_SENSITIVE_MARKERS = (
    "api_key", "apikey", "token", "access_token", "refresh_token", "authorization",
    "password", "secret", "cookie", "session", "credential", "filepath", "music_path",
    "library_path", "configured_path", "executable",
)


class StructuredLogSanitizer:
    """Bounded recursive sanitizer that never calls arbitrary ``repr``."""

    def __init__(self, max_depth=5, max_items=40, max_string_length=2000):
        if not all(isinstance(value, int) and value > 0 for value in (max_depth, max_items, max_string_length)):
            raise ValueError("Los limites del sanitizador deben ser enteros positivos.")
        self.max_depth, self.max_items, self.max_string_length = max_depth, max_items, max_string_length

    def sanitize(self, value, depth=0, key=None):
        if key is not None and self._sensitive(key):
            return "[REDACTED]"
        if depth >= self.max_depth:
            return "[TRUNCATED_DEPTH]"
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return value[: self.max_string_length] + ("[TRUNCATED]" if len(value) > self.max_string_length else "")
        if isinstance(value, Path):
            return f"<path:{value.name}>"
        if isinstance(value, dict):
            return {
                self._safe_key(item_key): self.sanitize(item_value, depth + 1, item_key)
                for item_key, item_value in list(value.items())[: self.max_items]
            }
        if isinstance(value, (tuple, list, set, frozenset)):
            return [self.sanitize(item, depth + 1) for item in list(value)[: self.max_items]]
        return f"<{type(value).__name__}>"

    @staticmethod
    def _safe_key(value):
        return value if isinstance(value, str) else f"<{type(value).__name__}>"

    @staticmethod
    def _sensitive(value):
        normalized = str(value).casefold().replace("-", "_")
        return any(marker in normalized for marker in _SENSITIVE_MARKERS)


class JSONLinesFormatter(logging.Formatter):
    """One safe, deterministic JSON object for each record."""

    def __init__(self, sanitizer=None, version=VERSION):
        super().__init__()
        self._sanitizer = sanitizer or StructuredLogSanitizer()
        self._version = version

    def format(self, record):
        message = record.msg if isinstance(record.msg, str) else f"<{type(record.msg).__name__}>"
        event = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": self._sanitizer.sanitize(message),
            "version": self._version,
            "process_id": os.getpid(),
            "thread_name": current_thread().name,
        }
        for key in ("event_name", "component", "operation_id", "exception_type"):
            value = getattr(record, key, None)
            if value is not None:
                event[key] = self._sanitizer.sanitize(value, key=key)
        context = getattr(record, "context", None)
        if context is not None:
            event["context"] = self._sanitizer.sanitize(context)
        if record.exc_info:
            event["exception_type"] = record.exc_info[0].__name__
            event["traceback"] = self._sanitizer.sanitize("".join(traceback.format_exception(*record.exc_info)))
        return json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class DiagnosticsExportResultDTO:
    filepath: str
    sha256: str
    size_bytes: int
    included_files: tuple[str, ...]
    errors: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.filepath, str) or not self.filepath.strip():
            raise DiagnosticsExportError("La ruta de exportacion es obligatoria.")
        if not isinstance(self.sha256, str) or len(self.sha256) != 64:
            raise DiagnosticsExportError("El checksum de diagnostico no es valido.")
        if not isinstance(self.size_bytes, int) or self.size_bytes < 1:
            raise DiagnosticsExportError("El tamano de diagnostico no es valido.")
        if not isinstance(self.included_files, tuple) or not all(isinstance(item, str) for item in self.included_files):
            raise DiagnosticsExportError("El manifiesto de diagnostico no es valido.")


class AppLoggingService:
    """Owns exactly one rotating handler for the ``djplus`` logger hierarchy."""

    LOGGER_NAME = "djplus"
    LOG_FILENAME = "djplus.jsonl"

    def __init__(self, settings=None, sanitizer=None, version=VERSION, replace_func=None):
        self._sanitizer = sanitizer or StructuredLogSanitizer()
        self._version, self._replace = version, replace_func or os.replace
        self._lock, self._handler, self._settings = RLock(), None, None
        self._hooks_installed, self._previous_sys_hook, self._previous_thread_hook = False, None, None
        self._hook_state = local()
        if settings is not None:
            self.configure(settings)

    def configure(self, settings):
        if not isinstance(settings, LoggingSettingsDTO):
            raise TypeError("AppLoggingService.configure requiere LoggingSettingsDTO.")
        with self._lock:
            directory = Path(settings.directory).expanduser()
            try:
                directory.mkdir(parents=True, exist_ok=True)
                handler = RotatingFileHandler(
                    directory / self.LOG_FILENAME, maxBytes=settings.max_bytes, backupCount=settings.retained_files,
                    encoding="utf-8", delay=True,
                )
            except OSError as error:
                raise LoggingConfigurationError("No se pudo configurar el directorio de logs DJPlus.") from error
            handler.setFormatter(JSONLinesFormatter(self._sanitizer if settings.redact_sensitive else StructuredLogSanitizer(), self._version))
            handler._djplus_structured_handler = True
            root = logging.getLogger(self.LOGGER_NAME)
            root.setLevel(getattr(logging, settings.level))
            root.propagate = False
            self._close_owned_handlers_locked(root)
            root.addHandler(handler)
            self._handler, self._settings = handler, settings
            return self

    def get_logger(self, component=None):
        name = self.LOGGER_NAME if component is None else f"{self.LOGGER_NAME}.{str(component).strip('.')}"
        return logging.getLogger(name)

    def get_log_directory(self):
        return Path(self._settings.directory) if self._settings is not None else None

    def get_current_log_file(self):
        directory = self.get_log_directory()
        return directory / self.LOG_FILENAME if directory is not None else None

    def flush(self):
        with self._lock:
            if self._handler is not None:
                self._handler.flush()

    def shutdown(self):
        with self._lock:
            self._close_handler_locked()
            self._restore_exception_hooks_locked()

    def install_exception_hooks(self):
        with self._lock:
            if self._hooks_installed:
                return
            self._previous_sys_hook = sys.excepthook
            self._previous_thread_hook = getattr(__import__("threading"), "excepthook", None)
            sys.excepthook = self._sys_hook
            if self._previous_thread_hook is not None:
                __import__("threading").excepthook = self._thread_hook
            self._hooks_installed = True

    def export_diagnostics(self, destination_path, settings_service=None, ffmpeg_diagnostics=None, database_status=None, max_bytes=256 * 1024):
        if not isinstance(max_bytes, int) or not 1024 <= max_bytes <= 10 * 1024 * 1024:
            raise DiagnosticsExportError("max_bytes de diagnostico no es valido.")
        destination = Path(destination_path)
        config = settings_service.export_sanitized() if settings_service is not None else {}
        if isinstance(config, dict):
            library = config.get("library")
            if isinstance(library, dict) and "music_paths" in library:
                library["music_paths"] = ["[REDACTED_PATH]" for _item in library["music_paths"]]
        ffmpeg = self._resolve_diagnostics(ffmpeg_diagnostics)
        manifest, logs = self._recent_logs(max_bytes // 2)
        payload = {
            "version": self._version,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "configuration": self._sanitizer.sanitize(config),
            "ffmpeg": self._sanitizer.sanitize(ffmpeg),
            "database": self._sanitizer.sanitize(database_status or {"status": "not_collected"}),
            "recent_logs": logs,
            "manifest": manifest,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        while len(encoded) > max_bytes and payload["recent_logs"]:
            payload["recent_logs"] = payload["recent_logs"][1:]
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        if len(encoded) > max_bytes:
            raise DiagnosticsExportError("La exportacion diagnostica excede el limite configurado.")
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
                self._replace(temporary, destination)
            except OSError:
                try: os.unlink(temporary)
                except OSError: pass
                raise
        except OSError as error:
            raise DiagnosticsExportError("No se pudo exportar el diagnostico de forma atomica.") from error
        return DiagnosticsExportResultDTO(str(destination), hashlib.sha256(encoded).hexdigest(), len(encoded), tuple(manifest))

    def _recent_logs(self, max_bytes):
        directory = self.get_log_directory()
        if directory is None or not directory.is_dir():
            return [], []
        candidates = [directory / self.LOG_FILENAME] + [directory / f"{self.LOG_FILENAME}.{index}" for index in range(1, (self._settings.retained_files if self._settings else 0) + 1)]
        manifest, lines, remaining = [], [], max_bytes
        for path in candidates:
            if not path.is_file():
                continue
            manifest.append(path.name)
            try:
                for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()[-100:]):
                    encoded = line.encode("utf-8", "replace")
                    if len(encoded) > remaining:
                        break
                    lines.append(self._safe_log_line(line)); remaining -= len(encoded)
            except OSError:
                continue
        return manifest, list(reversed(lines))

    def _safe_log_line(self, line):
        try:
            return self._sanitizer.sanitize(json.loads(line))
        except (TypeError, ValueError, json.JSONDecodeError):
            return "[UNPARSEABLE_LOG_LINE]"

    @staticmethod
    def _resolve_diagnostics(value):
        if value is None:
            return {"status": "not_collected"}
        try:
            value = value() if callable(value) else value
        except Exception as error:
            return {"status": "error", "exception_type": type(error).__name__}
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        return value

    def _sys_hook(self, exception_type, value, trace):
        self._log_unhandled(exception_type, value, trace, "sys")
        if self._previous_sys_hook is not None:
            self._previous_sys_hook(exception_type, value, trace)

    def _thread_hook(self, args):
        self._log_unhandled(args.exc_type, args.exc_value, args.exc_traceback, "thread")
        if self._previous_thread_hook is not None:
            self._previous_thread_hook(args)

    def _log_unhandled(self, exception_type, value, trace, source):
        if getattr(self._hook_state, "active", False):
            return
        self._hook_state.active = True
        try:
            self.get_logger("runtime").error("Unhandled exception", exc_info=(exception_type, value, trace), extra={"event_name": "unhandled_exception", "component": source, "exception_type": exception_type.__name__})
        except Exception:
            pass
        finally:
            self._hook_state.active = False

    def _close_handler_locked(self):
        if self._handler is None:
            return
        root = logging.getLogger(self.LOGGER_NAME)
        root.removeHandler(self._handler)
        try: self._handler.flush()
        finally: self._handler.close()
        self._handler = None

    @staticmethod
    def _close_owned_handlers_locked(root):
        """Remove every previous canonical handler, including another service instance."""
        for handler in tuple(root.handlers):
            if not getattr(handler, "_djplus_structured_handler", False):
                continue
            root.removeHandler(handler)
            try:
                handler.flush()
            finally:
                handler.close()

    def _restore_exception_hooks_locked(self):
        if not self._hooks_installed:
            return
        sys.excepthook = self._previous_sys_hook
        if self._previous_thread_hook is not None:
            __import__("threading").excepthook = self._previous_thread_hook
        self._hooks_installed = False
