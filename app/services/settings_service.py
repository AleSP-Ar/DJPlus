"""Versioned, safe local preferences without credentials or UI dependencies."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
from threading import RLock
from app.core.user_paths import get_user_data_paths

from .audio_decoder import OFFICIAL_AUDIO_FORMAT_ORDER
from .assistant_provider import ProviderConfigDTO
from .audio_analysis_service import AudioFileMusicAnalysisService, PCMFeatureExtractor, PCMKeyAnalyzer, WaveAudioAnalyzer
from .execution_hardening import ExecutionHardeningConfigDTO
from .ffmpeg_audio_decoder import FFmpegDecoderConfigDTO, FFmpegResolver


CURRENT_SETTINGS_SCHEMA_VERSION = 3
DEFAULT_ASSISTANT_MODEL = "llama3.2"
_SENSITIVE_MARKERS = ("api_key", "apikey", "token", "secret", "password", "credential", "private_key")
_KNOWN_EXTENSIONS = (".mp3", ".flac", ".aif", ".aiff", ".wav", ".m4a")
_LOGGER = logging.getLogger("djplus.settings")
_BASE_LOGGER = logging.getLogger("djplus")
if not any(isinstance(handler, logging.NullHandler) for handler in _BASE_LOGGER.handlers):
    _BASE_LOGGER.addHandler(logging.NullHandler())


class SettingsError(ValueError):
    """Base class for safe settings failures."""


class SettingsValidationError(SettingsError):
    """Raised when a persisted or supplied value is outside the contract."""


class SettingsLoadError(SettingsError):
    """Raised when configuration cannot be read without controlled recovery."""


class SettingsMigrationError(SettingsError):
    """Raised when an older settings schema cannot be upgraded safely."""


class SettingsFutureVersionError(SettingsMigrationError):
    """Raised when settings were written by a newer application."""


class SettingsPermissionError(SettingsError):
    """Raised when local settings cannot be written atomically."""


def _text(value, name, *, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise SettingsValidationError(f"{name} debe ser texto no vacio.")
    return value.strip() if not allow_empty else value


def _positive_int(value, name, low, high):
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise SettingsValidationError(f"{name} debe estar entre {low} y {high}.")
    return value


def _normalize_path(value, name):
    text = _text(value, name)
    if "\x00" in text:
        raise SettingsValidationError(f"{name} no puede contener NUL.")
    return os.path.normpath(os.path.expanduser(text))


def _safe_option_name(name):
    normalized = _text(name, "El nombre de opcion").casefold().replace("-", "_")
    if any(marker in normalized for marker in _SENSITIVE_MARKERS):
        raise SettingsValidationError("Las opciones del asistente no pueden contener secretos.")
    return normalized


@dataclass(frozen=True)
class GeneralSettingsDTO:
    locale: str = "es-AR"
    theme: str = "system"
    confirm_dangerous_actions: bool = True

    def __post_init__(self):
        _text(self.locale, "locale")
        if self.theme not in {"system", "light", "dark"}:
            raise SettingsValidationError("theme debe ser system, light o dark.")
        if not isinstance(self.confirm_dangerous_actions, bool):
            raise SettingsValidationError("confirm_dangerous_actions debe ser booleano.")


@dataclass(frozen=True)
class LibrarySettingsDTO:
    music_paths: tuple[str, ...] = ()
    scan_on_start: bool = False
    supported_formats: tuple[str, ...] = _KNOWN_EXTENSIONS
    page_size: int = 100
    result_limit: int = 1000
    key_notation: str = "both"
    recommendation_min_score: int = 45

    def __post_init__(self):
        if not isinstance(self.music_paths, tuple):
            raise SettingsValidationError("music_paths debe ser una tupla.")
        normalized = tuple(_normalize_path(item, "Ruta musical") for item in self.music_paths)
        if len(normalized) != len(set(item.casefold() for item in normalized)):
            raise SettingsValidationError("music_paths no puede contener rutas duplicadas.")
        object.__setattr__(self, "music_paths", normalized)
        if not isinstance(self.scan_on_start, bool):
            raise SettingsValidationError("scan_on_start debe ser booleano.")
        if not isinstance(self.supported_formats, tuple) or not self.supported_formats:
            raise SettingsValidationError("supported_formats debe tener extensiones.")
        formats = tuple(item.casefold() for item in self.supported_formats)
        if any(item not in _KNOWN_EXTENSIONS for item in formats) or len(set(formats)) != len(formats):
            raise SettingsValidationError("supported_formats contiene extensiones invalidas o duplicadas.")
        object.__setattr__(self, "supported_formats", formats)
        _positive_int(self.page_size, "page_size", 1, 1000)
        _positive_int(self.result_limit, "result_limit", 1, 100000)
        if self.key_notation not in {"camelot", "musical", "both"}:
            raise SettingsValidationError("key_notation debe ser camelot, musical o both.")
        _positive_int(self.recommendation_min_score, "recommendation_min_score", 1, 100)


@dataclass(frozen=True)
class AnalysisSettingsDTO:
    max_concurrency: int = 1
    block_frames: int = 1024
    timeout_seconds: int = 30
    auto_analysis_enabled: bool = False
    format_priority: tuple[str, ...] = OFFICIAL_AUDIO_FORMAT_ORDER

    def __post_init__(self):
        _positive_int(self.max_concurrency, "max_concurrency", 1, 4)
        _positive_int(self.block_frames, "block_frames", 64, 262144)
        _positive_int(self.timeout_seconds, "timeout_seconds", 1, 120)
        if not isinstance(self.auto_analysis_enabled, bool):
            raise SettingsValidationError("auto_analysis_enabled debe ser booleano.")
        if self.format_priority != OFFICIAL_AUDIO_FORMAT_ORDER:
            raise SettingsValidationError("format_priority debe respetar MP3, FLAC, AIFF/AIF y WAV.")


@dataclass(frozen=True)
class FFmpegSettingsDTO:
    configured_path: str | None = None
    allow_path: bool = True
    allow_bundled: bool = True
    detection_timeout_seconds: int = 15
    validate_bundled_checksum: bool = True

    def __post_init__(self):
        if self.configured_path is not None:
            object.__setattr__(self, "configured_path", _normalize_path(self.configured_path, "Ruta configurada de FFmpeg"))
        if not isinstance(self.allow_path, bool) or not isinstance(self.allow_bundled, bool):
            raise SettingsValidationError("Las fuentes FFmpeg deben ser booleanas.")
        _positive_int(self.detection_timeout_seconds, "detection_timeout_seconds", 1, 120)
        if not isinstance(self.validate_bundled_checksum, bool):
            raise SettingsValidationError("validate_bundled_checksum debe ser booleano.")
        if self.allow_bundled and not self.validate_bundled_checksum:
            raise SettingsValidationError("El runtime bundled requiere validacion de checksum.")


@dataclass(frozen=True)
class AssistantSettingsDTO:
    provider: str = "ollama"
    model: str = DEFAULT_ASSISTANT_MODEL
    timeout_ms: int = 30000
    tool_limit: int = 8
    options: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        _text(self.provider, "provider")
        _text(self.model, "model")
        _positive_int(self.timeout_ms, "timeout_ms", 1, 120000)
        _positive_int(self.tool_limit, "tool_limit", 1, 128)
        if not isinstance(self.options, tuple):
            raise SettingsValidationError("options debe ser una tupla inmutable.")
        normalized = tuple((_safe_option_name(name), _text(value, "Valor de opcion", allow_empty=True)) for name, value in self.options)
        if len({name for name, _value in normalized}) != len(normalized):
            raise SettingsValidationError("options no puede repetir claves.")
        object.__setattr__(self, "options", normalized)


@dataclass(frozen=True)
class PreviewPlayerSettingsDTO:
    """Persisted session preferences; device IDs are plain serialized strings."""

    volume: float = 0.70
    output_device_id: str | None = None
    output_device_description: str | None = None

    def __post_init__(self):
        if not isinstance(self.volume, (int, float)) or isinstance(self.volume, bool) or not 0.0 <= float(self.volume) <= 1.0:
            raise SettingsValidationError("preview_player.volume debe estar entre 0.0 y 1.0.")
        object.__setattr__(self, "volume", float(self.volume))
        for name in ("output_device_id", "output_device_description"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 512):
                raise SettingsValidationError(f"preview_player.{name} debe ser texto acotado o nulo.")
            if isinstance(value, str): object.__setattr__(self, name, value.strip())


@dataclass(frozen=True)
class LoggingSettingsDTO:
    level: str = "INFO"
    directory: str = "logs"
    max_bytes: int = 5 * 1024 * 1024
    retained_files: int = 5
    redact_sensitive: bool = True

    def __post_init__(self):
        if _text(self.level, "level").upper() not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise SettingsValidationError("level de logging no es valido.")
        object.__setattr__(self, "level", self.level.upper())
        object.__setattr__(self, "directory", _normalize_path(self.directory, "Directorio de logs"))
        _positive_int(self.max_bytes, "max_bytes", 1024, 1024 * 1024 * 1024)
        _positive_int(self.retained_files, "retained_files", 1, 100)
        if not isinstance(self.redact_sensitive, bool):
            raise SettingsValidationError("redact_sensitive debe ser booleano.")


@dataclass(frozen=True)
class BackupSettingsDTO:
    directory: str = "backups"
    retention: int = 7
    max_age_days: int | None = None
    retain_pre_action: bool = True
    auto_backup_enabled: bool = False
    verify_checksum: bool = True

    def __post_init__(self):
        object.__setattr__(self, "directory", _normalize_path(self.directory, "Directorio de backups"))
        _positive_int(self.retention, "retention", 1, 3650)
        if self.max_age_days is not None:
            _positive_int(self.max_age_days, "max_age_days", 1, 36500)
        if not isinstance(self.retain_pre_action, bool) or not isinstance(self.auto_backup_enabled, bool) or not isinstance(self.verify_checksum, bool):
            raise SettingsValidationError("Las opciones de backup deben ser booleanas.")


@dataclass(frozen=True)
class AppSettingsDTO:
    schema_version: int = CURRENT_SETTINGS_SCHEMA_VERSION
    general: GeneralSettingsDTO = GeneralSettingsDTO()
    library: LibrarySettingsDTO = LibrarySettingsDTO()
    analysis: AnalysisSettingsDTO = AnalysisSettingsDTO()
    ffmpeg: FFmpegSettingsDTO = FFmpegSettingsDTO()
    assistant: AssistantSettingsDTO = AssistantSettingsDTO()
    preview_player: PreviewPlayerSettingsDTO = PreviewPlayerSettingsDTO()
    logging: LoggingSettingsDTO = LoggingSettingsDTO()
    backup: BackupSettingsDTO = BackupSettingsDTO()

    def __post_init__(self):
        if self.schema_version != CURRENT_SETTINGS_SCHEMA_VERSION:
            raise SettingsValidationError("schema_version no coincide con la version actual.")
        for value, expected in (
            (self.general, GeneralSettingsDTO), (self.library, LibrarySettingsDTO), (self.analysis, AnalysisSettingsDTO),
            (self.ffmpeg, FFmpegSettingsDTO), (self.assistant, AssistantSettingsDTO), (self.preview_player, PreviewPlayerSettingsDTO),
            (self.logging, LoggingSettingsDTO), (self.backup, BackupSettingsDTO),
        ):
            if not isinstance(value, expected):
                raise SettingsValidationError("La configuracion contiene una seccion invalida.")


class SettingsService:
    """Canonical settings boundary with atomic JSON persistence and migration."""

    def __init__(self, config_path=None, appdata_path=None, replace_func=None, copy_func=None):
        if config_path is not None and appdata_path is not None:
            raise TypeError("Use config_path o appdata_path, no ambos.")
        if config_path is None:
            config_path = (Path(appdata_path) / "DJPlus" / "config.json") if appdata_path is not None else get_user_data_paths().config
        self._path = Path(config_path).expanduser()
        self._replace = replace_func or os.replace
        self._copy = copy_func or shutil.copy2
        self._lock = RLock()
        self._config = None

    def get_config_path(self):
        return self._path

    def defaults(self):
        root = self._path.parent
        return AppSettingsDTO(logging=LoggingSettingsDTO(directory=str(root / "logs")), backup=BackupSettingsDTO(directory=str(root / "backups")))

    def load(self, recover_corrupt=True):
        with self._lock:
            if not self._path.is_file():
                self._config = self.defaults()
                _LOGGER.info("Settings defaults loaded", extra={"event_name": "settings_defaults", "component": "settings"})
                return self._config
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                if not recover_corrupt:
                    raise SettingsLoadError("La configuracion no se puede leer como JSON valido.") from error
                self._backup_file("corrupt")
                self._config = self.defaults()
                _LOGGER.warning("Corrupt settings recovered", extra={"event_name": "settings_corrupt_recovered", "component": "settings", "context": {"exception_type": type(error).__name__}})
                return self._config
            config = self._from_mapping(raw, migrate=True)
            self._config = config
            _LOGGER.info("Settings loaded", extra={"event_name": "settings_loaded", "component": "settings", "context": {"schema_version": config.schema_version}})
            return config

    def save(self, config=None):
        with self._lock:
            validated = self.validate(config if config is not None else self.get())
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise SettingsPermissionError("No se pudo crear el directorio de configuracion.") from error
            descriptor, temporary = tempfile.mkstemp(prefix=f".{self._path.name}.", suffix=".tmp", dir=self._path.parent)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                    json.dump(self._to_mapping(validated), stream, ensure_ascii=False, indent=2, sort_keys=True)
                    stream.flush()
                    os.fsync(stream.fileno())
                self._replace(temporary, self._path)
            except (OSError, PermissionError) as error:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise SettingsPermissionError("No se pudo guardar la configuracion de forma atomica.") from error
            self._config = validated
            _LOGGER.info("Settings saved", extra={"event_name": "settings_saved", "component": "settings", "context": {"schema_version": validated.schema_version}})
            return validated

    def reset_to_defaults(self):
        return self.save(self.defaults())

    def get(self):
        with self._lock:
            if self._config is None:
                return self.load()
            return self._config

    def update(self, values):
        if not isinstance(values, dict):
            raise SettingsValidationError("update requiere un diccionario parcial.")
        with self._lock:
            merged = self._merge(self._to_mapping(self.get()), values)
            return self.save(self.validate(merged))

    def validate(self, config):
        if isinstance(config, AppSettingsDTO):
            return config
        return self._from_mapping(config, migrate=False)

    def export_sanitized(self):
        return self._redact(self._to_mapping(self.get()))

    def ffmpeg_decoder_config(self):
        value = self.get().ffmpeg
        return FFmpegDecoderConfigDTO(value.configured_path, value.detection_timeout_seconds)

    def create_ffmpeg_resolver(self, **overrides):
        value = self.get().ffmpeg
        return FFmpegResolver(
            self.ffmpeg_decoder_config(), allow_path=value.allow_path, allow_bundled=value.allow_bundled,
            **overrides,
        )

    def analysis_hardening_config(self):
        value = self.get().analysis
        return ExecutionHardeningConfigDTO(timeout_ms=value.timeout_seconds * 1000, max_concurrency=value.max_concurrency)

    def create_audio_analysis_service(self, decoder_registry=None):
        frames = self.get().analysis.block_frames
        features, key = PCMFeatureExtractor(), PCMKeyAnalyzer()
        features.block_frames = frames; key.block_frames = frames
        return AudioFileMusicAnalysisService(analyzer=WaveAudioAnalyzer(features, key, decoder_registry))

    def assistant_provider_config(self):
        value = self.get().assistant
        return ProviderConfigDTO(model=value.model, timeout_ms=value.timeout_ms)

    def _from_mapping(self, raw, migrate):
        if not isinstance(raw, dict):
            raise SettingsValidationError("La raiz de configuracion debe ser un objeto JSON.")
        raw = dict(raw)
        version = raw.get("schema_version", 1)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise SettingsMigrationError("schema_version no es valida.")
        if version > CURRENT_SETTINGS_SCHEMA_VERSION:
            raise SettingsFutureVersionError("La configuracion fue creada por una version mas reciente de DJPlus.")
        if migrate and version < CURRENT_SETTINGS_SCHEMA_VERSION:
            self._backup_file(f"v{version}")
            while version < CURRENT_SETTINGS_SCHEMA_VERSION:
                raw = self._migrate_once(version, raw)
                version += 1
            raw["schema_version"] = version
            config = self._from_mapping(raw, migrate=False)
            self.save(config)
            return config
        if version != CURRENT_SETTINGS_SCHEMA_VERSION:
            raise SettingsMigrationError("La configuracion requiere una migracion controlada.")
        allowed = {"schema_version", "general", "library", "analysis", "ffmpeg", "assistant", "preview_player", "logging", "backup"}
        self._reject_unknown(raw, allowed, "raiz")
        defaults = self.defaults()
        return AppSettingsDTO(
            general=self._section(raw.get("general", {}), GeneralSettingsDTO, defaults.general, "general"),
            library=self._section(raw.get("library", {}), LibrarySettingsDTO, defaults.library, "library"),
            analysis=self._section(raw.get("analysis", {}), AnalysisSettingsDTO, defaults.analysis, "analysis"),
            ffmpeg=self._section(raw.get("ffmpeg", {}), FFmpegSettingsDTO, defaults.ffmpeg, "ffmpeg"),
            assistant=self._assistant_section(raw.get("assistant", {}), defaults.assistant),
            preview_player=self._section(raw.get("preview_player", {}), PreviewPlayerSettingsDTO, defaults.preview_player, "preview_player"),
            logging=self._section(raw.get("logging", {}), LoggingSettingsDTO, defaults.logging, "logging"),
            backup=self._section(raw.get("backup", {}), BackupSettingsDTO, defaults.backup, "backup"),
        )

    def _section(self, raw, dto_type, defaults, label):
        if not isinstance(raw, dict):
            raise SettingsValidationError(f"{label} debe ser un objeto.")
        fields = set(dto_type.__dataclass_fields__)
        self._reject_unknown(raw, fields, label)
        values = asdict(defaults); values.update(raw)
        for key, value in tuple(values.items()):
            if isinstance(getattr(defaults, key), tuple) and isinstance(value, list):
                values[key] = tuple(value)
        return dto_type(**values)

    def _assistant_section(self, raw, defaults):
        if not isinstance(raw, dict):
            raise SettingsValidationError("assistant debe ser un objeto.")
        self._reject_unknown(raw, set(AssistantSettingsDTO.__dataclass_fields__), "assistant")
        values = asdict(defaults); values.update(raw)
        options = values.get("options", ())
        if isinstance(options, dict):
            options = tuple(options.items())
        elif isinstance(options, list):
            options = tuple(tuple(item) for item in options)
        values["options"] = options
        return AssistantSettingsDTO(**values)

    @staticmethod
    def _reject_unknown(raw, allowed, label):
        extra = sorted(set(raw) - set(allowed))
        if extra:
            raise SettingsValidationError(f"Campos desconocidos en {label}: {', '.join(extra)}.")

    @staticmethod
    def _merge(base, patch):
        result = dict(base)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = SettingsService._merge(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def _redact(value):
        if isinstance(value, dict):
            return {key: "<redacted>" if any(marker in key.casefold() for marker in _SENSITIVE_MARKERS) else SettingsService._redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [SettingsService._redact(item) for item in value]
        return value

    @staticmethod
    def _to_mapping(config):
        if not isinstance(config, AppSettingsDTO):
            raise SettingsValidationError("La configuracion debe ser AppSettingsDTO.")
        result = asdict(config)
        result["assistant"]["options"] = dict(config.assistant.options)
        return result

    def _backup_file(self, suffix):
        if not self._path.is_file():
            return None
        target = self._path.with_name(f"{self._path.name}.{suffix}.backup")
        try:
            self._copy(self._path, target)
        except OSError as error:
            raise SettingsLoadError("No se pudo crear respaldo de configuracion.") from error
        return target

    @staticmethod
    def _migrate_once(version, raw):
        migrated = json.loads(json.dumps(raw))
        if version == 1:
            general = migrated.setdefault("general", {})
            if not isinstance(general, dict):
                raise SettingsMigrationError("La seccion general antigua es invalida.")
            general.setdefault("theme", "system")
            general.setdefault("confirm_dangerous_actions", True)
        elif version == 2:
            migrated.setdefault("preview_player", {"volume": 0.70, "output_device_id": None, "output_device_description": None})
        else:
            raise SettingsMigrationError(f"No existe migracion desde schema_version {version}.")
        return migrated
