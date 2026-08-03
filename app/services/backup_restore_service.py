"""Verified local ZIP backups and deliberately confirmed SQLite restores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import secrets
import sqlite3
import tempfile
from threading import Lock, RLock
import zipfile

from app.version import VERSION
from app.database.migrations import MIGRATIONS, run_migrations
from .settings_service import BackupSettingsDTO, SettingsService, SettingsValidationError


BACKUP_FORMAT_VERSION = 1
_DATABASE_NAME = "database.sqlite"
_SETTINGS_NAME = "settings.json"
_MANIFEST_NAME = "manifest.json"
_CHECKSUMS_NAME = "checksums.sha256"
_REASONS = {"manual", "automatic", "pre_action", "migration"}
_STATUSES = {"valid", "valid_with_warnings", "incompatible", "corrupt", "unsafe"}


class BackupError(RuntimeError):
    """Base controlled error for local backup operations."""


class BackupCreationError(BackupError):
    """Raised when a backup cannot be created atomically."""


class BackupVerificationError(BackupError):
    """Raised when a backup is corrupt or incomplete."""


class BackupSecurityError(BackupVerificationError):
    """Raised when a ZIP member is unsafe for local extraction."""


class BackupIncompatibleError(BackupVerificationError):
    """Raised for a future or unsupported backup/schema format."""


class RestoreError(BackupError):
    """Raised when a prepared restore cannot complete safely."""


class RestoreConfirmationError(RestoreError):
    """Raised unless a restore plan's one-time confirmation token matches."""


class RestoreBusyError(RestoreError):
    """Raised when another restore is already active."""


@dataclass(frozen=True)
class BackupRequestDTO:
    reason: str = "manual"
    include_database: bool = True
    include_settings: bool = True
    operation_id: str | None = None
    cancellation_token: object | None = None

    def __post_init__(self):
        if self.reason not in _REASONS:
            raise ValueError("La razon de backup no es valida.")
        if not isinstance(self.include_database, bool) or not isinstance(self.include_settings, bool):
            raise ValueError("Los componentes de backup deben ser booleanos.")
        if not self.include_database and not self.include_settings:
            raise ValueError("El backup debe incluir base de datos o configuracion.")
        if self.operation_id is not None and (not isinstance(self.operation_id, str) or not self.operation_id.strip()):
            raise ValueError("operation_id debe ser texto o nulo.")


@dataclass(frozen=True)
class BackupManifestDTO:
    backup_format_version: int
    backup_id: str
    created_at_utc: str
    djplus_version: str
    python_version: str
    platform: str
    database_schema_version: str | None
    settings_schema_version: int | None
    files: tuple[tuple[str, int, str], ...]
    reason: str
    consistency: str
    warnings: tuple[str, ...] = ()
    minimum_compatible_version: str = VERSION

    def __post_init__(self):
        if self.backup_format_version != BACKUP_FORMAT_VERSION:
            raise BackupIncompatibleError("La version de formato de backup no es compatible.")
        if not isinstance(self.backup_id, str) or len(self.backup_id) < 8:
            raise BackupVerificationError("El identificador de backup no es valido.")
        if self.reason not in _REASONS or self.consistency not in {"consistent", "partial"}:
            raise BackupVerificationError("El manifiesto de backup no es valido.")
        if not self.files or any(not isinstance(name, str) or size < 0 or len(checksum) != 64 for name, size, checksum in self.files):
            raise BackupVerificationError("Los archivos declarados en el manifiesto no son validos.")


@dataclass(frozen=True)
class BackupVerificationDTO:
    status: str
    backup_id: str | None = None
    manifest: BackupManifestDTO | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def __post_init__(self):
        if self.status not in _STATUSES:
            raise ValueError("El estado de verificacion no es valido.")

    @property
    def valid(self):
        return self.status in {"valid", "valid_with_warnings"}


@dataclass(frozen=True)
class BackupResultDTO:
    success: bool
    backup_id: str | None
    filepath: str | None
    verification: BackupVerificationDTO | None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    cancelled: bool = False
    included_files: tuple[str, ...] = ()
    skipped_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class BackupEntryDTO:
    filepath: str
    backup_id: str | None
    created_at_utc: str | None
    reason: str | None
    size_bytes: int
    status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RestorePlanDTO:
    backup_path: str
    backup_id: str
    verification: BackupVerificationDTO
    replace_database: bool
    replace_settings: bool
    source_database_schema: str | None
    current_database_schema: str | None
    warnings: tuple[str, ...]
    required_actions: tuple[str, ...]
    confirmation_token: str


@dataclass(frozen=True)
class RestoreResultDTO:
    success: bool
    backup_id: str | None
    pre_action_backup_id: str | None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    restart_required: bool = False
    cancelled: bool = False


@dataclass(frozen=True)
class RetentionResultDTO:
    deleted_files: tuple[str, ...]
    retained_files: tuple[str, ...]
    warnings: tuple[str, ...] = ()


class BackupRestoreService:
    """Single local boundary for backup, verification, retention and restore."""

    def __init__(self, settings_service, database_path, logger=None, close_connections=None, migration_runner=None, clock=None):
        if not isinstance(settings_service, SettingsService):
            raise TypeError("BackupRestoreService requiere SettingsService.")
        self._settings_service = settings_service
        self._database_path = Path(database_path)
        self._logger = logger or logging.getLogger("djplus.backup")
        self._close_connections = close_connections or (lambda: None)
        self._migration_runner = migration_runner or self._migrate_path
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._backup_lock, self._restore_lock = RLock(), Lock()
        self._plans = {}

    def get_backup_directory(self):
        return Path(self._settings_service.get().backup.directory)

    def create_backup(self, request=None):
        request = request or BackupRequestDTO()
        if not isinstance(request, BackupRequestDTO):
            raise TypeError("create_backup requiere BackupRequestDTO.")
        with self._backup_lock:
            return self._create_backup_locked(request)

    def create_pre_action_backup(self, operation_id=None):
        return self.create_backup(BackupRequestDTO(reason="pre_action", operation_id=operation_id))

    def _create_backup_locked(self, request):
        started = self._clock()
        backup_id = secrets.token_hex(8)
        self._event("backup_started", backup_id, request, status="started")
        directory = self.get_backup_directory()
        temporary_dir = None
        temporary_zip = None
        warnings, included, skipped = [], [], []
        try:
            directory.mkdir(parents=True, exist_ok=True)
            self._check_cancel(request)
            temporary_dir = Path(tempfile.mkdtemp(prefix="djplus-backup-"))
            files = []
            database_schema = None
            if request.include_database:
                if self._database_path.is_file():
                    copied = temporary_dir / _DATABASE_NAME
                    self._sqlite_backup(copied, request)
                    database_schema = self._database_schema(copied)
                    files.append((_DATABASE_NAME, copied)); included.append(_DATABASE_NAME)
                else:
                    warnings.append("database_missing"); skipped.append(_DATABASE_NAME)
            self._check_cancel(request)
            settings_schema = None
            if request.include_settings:
                payload, setting_warnings = self._safe_settings_payload()
                warnings.extend(setting_warnings)
                if payload is not None:
                    target = temporary_dir / _SETTINGS_NAME
                    target.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
                    settings_schema = payload.get("schema_version")
                    files.append((_SETTINGS_NAME, target)); included.append(_SETTINGS_NAME)
                else:
                    skipped.append(_SETTINGS_NAME)
            if not files:
                raise BackupCreationError("No hay datos seguros para incluir en el backup.")
            self._check_cancel(request)
            manifest = BackupManifestDTO(
                BACKUP_FORMAT_VERSION, backup_id, self._iso(started), VERSION, platform.python_version(),
                platform.platform(), database_schema, settings_schema,
                tuple((name, path.stat().st_size, self._sha256_path(path)) for name, path in files),
                request.reason, "partial" if warnings else "consistent", tuple(sorted(set(warnings))), VERSION,
            )
            stamp = started.strftime("%Y%m%d_%H%M%S")
            destination = directory / f"DJPlus_Backup_{stamp}_{backup_id[:8]}.zip"
            if destination.exists():
                raise BackupCreationError("El nombre de backup ya existe.")
            temporary_zip = directory / f".{destination.name}.{backup_id}.tmp"
            self._write_zip(temporary_zip, files, manifest)
            self._check_cancel(request)
            verification = self.verify_backup(temporary_zip)
            if not verification.valid:
                raise BackupVerificationError("El backup temporal no supero la verificacion.")
            os.replace(temporary_zip, destination)
            temporary_zip = None
            result = BackupResultDTO(True, backup_id, str(destination), verification, tuple(warnings), (), False, tuple(included), tuple(skipped))
            self._event("backup_completed", backup_id, request, status=verification.status, size=destination.stat().st_size, duration_ms=self._duration_ms(started))
            return result
        except _Cancelled:
            result = BackupResultDTO(False, backup_id, None, None, tuple(warnings), ("cancelled",), True, tuple(included), tuple(skipped))
            self._event("backup_cancelled", backup_id, request, status="cancelled", duration_ms=self._duration_ms(started))
            return result
        except BackupError as error:
            self._event("backup_failed", backup_id, request, status="failed", duration_ms=self._duration_ms(started), exception_type=type(error).__name__)
            return BackupResultDTO(False, backup_id, None, None, tuple(warnings), (type(error).__name__,), False, tuple(included), tuple(skipped))
        except (OSError, sqlite3.Error, zipfile.BadZipFile, ValueError) as error:
            self._event("backup_failed", backup_id, request, status="failed", duration_ms=self._duration_ms(started), exception_type=type(error).__name__)
            return BackupResultDTO(False, backup_id, None, None, tuple(warnings), (type(error).__name__,), False, tuple(included), tuple(skipped))
        finally:
            if temporary_zip is not None:
                self._unlink(temporary_zip)
            if temporary_dir is not None:
                self._remove_tree(temporary_dir)

    def verify_backup(self, backup_path):
        path = Path(backup_path)
        try:
            if not path.is_file():
                raise BackupVerificationError("El archivo de backup no existe.")
            with zipfile.ZipFile(path, "r") as archive:
                names = archive.namelist()
                self._validate_zip_names(archive, names)
                if _MANIFEST_NAME not in names or _CHECKSUMS_NAME not in names:
                    raise BackupVerificationError("El ZIP no contiene manifiesto y checksums.")
                manifest = self._manifest_from_json(archive.read(_MANIFEST_NAME))
                expected = {name: (size, checksum) for name, size, checksum in manifest.files}
                allowed = set(expected) | {_MANIFEST_NAME, _CHECKSUMS_NAME}
                if set(names) != allowed:
                    raise BackupSecurityError("El ZIP contiene archivos no declarados o prohibidos.")
                self._validate_checksums_file(archive.read(_CHECKSUMS_NAME), expected, archive.read(_MANIFEST_NAME))
                for name, (size, checksum) in expected.items():
                    data = archive.read(name)
                    if len(data) != size or hashlib.sha256(data).hexdigest() != checksum:
                        raise BackupVerificationError("El checksum o tamano de un archivo no coincide.")
                warnings = list(manifest.warnings)
                if _DATABASE_NAME in expected:
                    with tempfile.TemporaryDirectory(prefix="djplus-verify-") as directory:
                        candidate = Path(directory) / _DATABASE_NAME
                        candidate.write_bytes(archive.read(_DATABASE_NAME))
                        self._validate_sqlite(candidate)
                        schema = self._database_schema(candidate)
                    if schema != manifest.database_schema_version:
                        raise BackupVerificationError("El schema SQLite no coincide con el manifiesto.")
                    current = self._current_schema()
                    if schema is not None and schema > current:
                        return BackupVerificationDTO("incompatible", manifest.backup_id, manifest, tuple(warnings), ("database_schema_future",))
                    if schema is not None and schema < current:
                        warnings.append("database_schema_migration_required")
                if _SETTINGS_NAME in expected:
                    raw = json.loads(archive.read(_SETTINGS_NAME).decode("utf-8"))
                    self._settings_service.validate(raw)
                    if raw.get("schema_version") != manifest.settings_schema_version:
                        raise BackupVerificationError("El schema de configuracion no coincide con el manifiesto.")
                return BackupVerificationDTO("valid_with_warnings" if warnings else "valid", manifest.backup_id, manifest, tuple(sorted(set(warnings))), ())
        except BackupIncompatibleError as error:
            return BackupVerificationDTO("incompatible", None, None, (), (type(error).__name__,))
        except BackupSecurityError as error:
            self._event("backup_verification_failed", None, None, status="unsafe", exception_type=type(error).__name__)
            return BackupVerificationDTO("unsafe", None, None, (), (type(error).__name__,))
        except (BackupVerificationError, zipfile.BadZipFile, OSError, UnicodeDecodeError, json.JSONDecodeError, sqlite3.Error, SettingsValidationError) as error:
            self._event("backup_verification_failed", None, None, status="corrupt", exception_type=type(error).__name__)
            return BackupVerificationDTO("corrupt", None, None, (), (type(error).__name__,))

    def inspect_backup(self, backup_path):
        return self.verify_backup(backup_path)

    def list_backups(self):
        directory = self.get_backup_directory()
        if not directory.is_dir():
            return ()
        entries = []
        for path in sorted(directory.glob("DJPlus_Backup_*.zip"), key=lambda item: item.name, reverse=True):
            if path.is_symlink() or not path.is_file():
                continue
            checked = self.verify_backup(path)
            manifest = checked.manifest
            entries.append(BackupEntryDTO(str(path), checked.backup_id, manifest.created_at_utc if manifest else None, manifest.reason if manifest else None, path.stat().st_size, checked.status, checked.warnings + checked.errors))
        return tuple(entries)

    def apply_retention(self, protected_paths=()):
        settings = self._settings_service.get().backup
        protected = {str(Path(item)) for item in protected_paths}
        entries = list(self.list_backups())
        retained, deleted, warnings = [], [], []
        now = self._clock()
        for index, entry in enumerate(entries):
            too_old = False
            if settings.max_age_days is not None and entry.created_at_utc:
                try:
                    created = datetime.fromisoformat(entry.created_at_utc.replace("Z", "+00:00"))
                    too_old = now - created > timedelta(days=settings.max_age_days)
                except ValueError:
                    warnings.append(f"invalid_date:{Path(entry.filepath).name}")
            if (index < settings.retention and not too_old) or entry.filepath in protected or (entry.reason == "pre_action" and settings.retain_pre_action):
                retained.append(entry.filepath); continue
            path = Path(entry.filepath)
            try:
                if path.is_symlink() or path.parent != self.get_backup_directory():
                    warnings.append(f"not_deleted:{path.name}"); retained.append(entry.filepath); continue
                path.unlink(); deleted.append(entry.filepath)
            except OSError:
                warnings.append(f"delete_failed:{path.name}"); retained.append(entry.filepath)
        result = RetentionResultDTO(tuple(deleted), tuple(retained), tuple(warnings))
        self._event("retention_completed", None, None, status="completed", count=len(deleted))
        return result

    def delete_backup(self, backup_path):
        path = Path(backup_path)
        directory = self.get_backup_directory()
        if path.parent != directory or path.is_symlink() or not path.name.startswith("DJPlus_Backup_") or path.suffix != ".zip":
            raise BackupSecurityError("Solo se pueden eliminar backups canonicos.")
        verification = self.verify_backup(path)
        if verification.status == "unsafe":
            raise BackupSecurityError("No se puede eliminar un ZIP inseguro mediante este servicio.")
        path.unlink()

    def plan_restore(self, backup_path, restore_database=True, restore_settings=True):
        if not restore_database and not restore_settings:
            raise RestoreError("Debe seleccionarse base de datos o configuracion.")
        verification = self.verify_backup(backup_path)
        if not verification.valid or verification.manifest is None:
            raise BackupVerificationError("El backup no es restaurable.")
        files = {name for name, _size, _checksum in verification.manifest.files}
        if restore_database and _DATABASE_NAME not in files:
            raise RestoreError("El backup no contiene base de datos.")
        if restore_settings and _SETTINGS_NAME not in files:
            raise RestoreError("El backup no contiene configuracion.")
        token = secrets.token_urlsafe(24)
        warnings = list(verification.warnings)
        if restore_database and verification.manifest.database_schema_version != self._current_schema():
            warnings.append("database_schema_migration_required")
        plan = RestorePlanDTO(str(Path(backup_path)), verification.manifest.backup_id, verification, restore_database, restore_settings,
            verification.manifest.database_schema_version, self._current_schema(), tuple(sorted(set(warnings))),
            ("verify_again", "create_pre_action_backup", "close_connections", "atomic_replace", "restart_recommended"), token)
        self._plans[token] = plan
        self._event("restore_planned", plan.backup_id, None, status="planned")
        return plan

    def restore_backup(self, plan, confirmation_token, cancellation_token=None):
        if not isinstance(plan, RestorePlanDTO) or self._plans.get(confirmation_token) != plan or confirmation_token != plan.confirmation_token:
            raise RestoreConfirmationError("La restauracion requiere un plan y confirmacion validos.")
        if not self._restore_lock.acquire(blocking=False):
            raise RestoreBusyError("Ya existe una restauracion en curso.")
        started = self._clock()
        temporary_dir = None
        pre_action = None
        try:
            if self._cancelled(cancellation_token):
                return RestoreResultDTO(False, plan.backup_id, None, plan.warnings, ("cancelled",), cancelled=True)
            verification = self.verify_backup(plan.backup_path)
            if not verification.valid:
                raise BackupVerificationError("El backup cambio o ya no es valido.")
            pre_action = self.create_pre_action_backup(operation_id=f"restore:{plan.backup_id}")
            if not pre_action.success or pre_action.verification is None or not pre_action.verification.valid:
                raise RestoreError("No se pudo crear el backup preventivo verificado.")
            self._event("pre_restore_backup_completed", pre_action.backup_id, None, status="completed")
            if self._cancelled(cancellation_token):
                return RestoreResultDTO(False, plan.backup_id, pre_action.backup_id, plan.warnings, ("cancelled",), cancelled=True)
            self._event("restore_started", plan.backup_id, None, status="started")
            temporary_dir = Path(tempfile.mkdtemp(prefix="djplus-restore-"))
            with zipfile.ZipFile(plan.backup_path, "r") as archive:
                names = set(archive.namelist())
                if plan.replace_database:
                    candidate = temporary_dir / _DATABASE_NAME
                    candidate.write_bytes(archive.read(_DATABASE_NAME))
                    self._validate_sqlite(candidate)
                    if self._database_schema(candidate) != self._current_schema():
                        self._migration_runner(candidate)
                        self._validate_sqlite(candidate)
                if plan.replace_settings:
                    config_candidate = temporary_dir / _SETTINGS_NAME
                    config_candidate.write_bytes(archive.read(_SETTINGS_NAME))
                    self._settings_service.validate(json.loads(config_candidate.read_text(encoding="utf-8")))
            if self._cancelled(cancellation_token):
                return RestoreResultDTO(False, plan.backup_id, pre_action.backup_id, plan.warnings, ("cancelled",), cancelled=True)
            self._close_connections()
            if plan.replace_database:
                self._atomic_replace(temporary_dir / _DATABASE_NAME, self._database_path)
            if plan.replace_settings:
                self._atomic_replace(temporary_dir / _SETTINGS_NAME, self._settings_service.get_config_path())
                self._settings_service.load(recover_corrupt=False)
            self._plans.pop(confirmation_token, None)
            result = RestoreResultDTO(True, plan.backup_id, pre_action.backup_id, plan.warnings, (), True)
            self._event("restore_completed", plan.backup_id, None, status="completed", duration_ms=self._duration_ms(started))
            return result
        except BackupError as error:
            self._event("restore_failed", plan.backup_id, None, status="failed", exception_type=type(error).__name__, duration_ms=self._duration_ms(started))
            return RestoreResultDTO(False, plan.backup_id, pre_action.backup_id if pre_action else None, plan.warnings, (type(error).__name__,))
        except (OSError, sqlite3.Error, zipfile.BadZipFile, ValueError, SettingsValidationError) as error:
            self._event("restore_failed", plan.backup_id, None, status="failed", exception_type=type(error).__name__, duration_ms=self._duration_ms(started))
            return RestoreResultDTO(False, plan.backup_id, pre_action.backup_id if pre_action else None, plan.warnings, (type(error).__name__,))
        finally:
            if temporary_dir is not None:
                self._remove_tree(temporary_dir)
            self._restore_lock.release()

    def _sqlite_backup(self, destination, request):
        source = sqlite3.connect(self._database_path)
        target = sqlite3.connect(destination)
        try:
            source.backup(target, pages=128, progress=lambda _status, _remaining, _total: self._check_cancel(request))
        finally:
            target.close(); source.close()
        self._validate_sqlite(destination)

    def _safe_settings_payload(self):
        path = self._settings_service.get_config_path()
        if not path.is_file():
            return None, ["settings_missing"]
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            self._settings_service.validate(raw)
            payload = self._settings_service.export_sanitized()
            if isinstance(payload.get("library"), dict):
                payload["library"]["music_paths"] = []
            return payload, ["settings_music_paths_omitted"]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, SettingsValidationError):
            return None, ["settings_corrupt_omitted"]

    def _write_zip(self, target, files, manifest):
        serialized_manifest = self._manifest_json(manifest)
        checksums = "".join(f"{checksum}  {name}\n" for name, _size, checksum in manifest.files)
        checksums += f"{hashlib.sha256(serialized_manifest).hexdigest()}  {_MANIFEST_NAME}\n"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name, path in files:
                archive.write(path, name)
            archive.writestr(_MANIFEST_NAME, serialized_manifest)
            archive.writestr(_CHECKSUMS_NAME, checksums)
        with open(target, "r+b") as stream:
            os.fsync(stream.fileno())

    def _manifest_from_json(self, raw):
        value = json.loads(raw.decode("utf-8"))
        required = {"backup_format_version", "backup_id", "created_at_utc", "djplus_version", "python_version", "platform", "database_schema_version", "settings_schema_version", "files", "reason", "consistency", "warnings", "minimum_compatible_version"}
        if set(value) != required or not isinstance(value["files"], list):
            raise BackupVerificationError("El manifiesto no tiene el contrato esperado.")
        files = tuple((item["name"], item["size_bytes"], item["sha256"]) for item in value["files"] if isinstance(item, dict) and set(item) == {"name", "size_bytes", "sha256"})
        if len(files) != len(value["files"]):
            raise BackupVerificationError("El manifiesto contiene archivos invalidos.")
        return BackupManifestDTO(value["backup_format_version"], value["backup_id"], value["created_at_utc"], value["djplus_version"], value["python_version"], value["platform"], value["database_schema_version"], value["settings_schema_version"], files, value["reason"], value["consistency"], tuple(value["warnings"]), value["minimum_compatible_version"])

    @staticmethod
    def _manifest_json(manifest):
        value = {
            "backup_format_version": manifest.backup_format_version, "backup_id": manifest.backup_id,
            "created_at_utc": manifest.created_at_utc, "djplus_version": manifest.djplus_version,
            "python_version": manifest.python_version, "platform": manifest.platform,
            "database_schema_version": manifest.database_schema_version, "settings_schema_version": manifest.settings_schema_version,
            "files": [{"name": name, "size_bytes": size, "sha256": checksum} for name, size, checksum in manifest.files],
            "reason": manifest.reason, "consistency": manifest.consistency, "warnings": list(manifest.warnings),
            "minimum_compatible_version": manifest.minimum_compatible_version,
        }
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _validate_zip_names(archive, names):
        if len(names) != len(set(names)):
            raise BackupSecurityError("El ZIP contiene nombres duplicados.")
        for info in archive.infolist():
            name = info.filename
            if not name or name.startswith(("/", "\\")) or "\\" in name or ".." in Path(name).parts or Path(name).drive:
                raise BackupSecurityError("El ZIP contiene una ruta insegura.")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise BackupSecurityError("El ZIP contiene un enlace simbolico.")

    @staticmethod
    def _validate_checksums_file(raw, expected, manifest_bytes):
        declared = {}
        for line in raw.decode("utf-8").splitlines():
            checksum, separator, name = line.partition("  ")
            if not separator or len(checksum) != 64:
                raise BackupVerificationError("checksums.sha256 no es valido.")
            declared[name] = checksum
        for name, (_size, checksum) in expected.items():
            if declared.get(name) != checksum:
                raise BackupVerificationError("checksums.sha256 no coincide con el manifiesto.")
        if declared.get(_MANIFEST_NAME) != hashlib.sha256(manifest_bytes).hexdigest():
            raise BackupVerificationError("checksums.sha256 no cubre el manifiesto.")

    @staticmethod
    def _validate_sqlite(path):
        connection = sqlite3.connect(path)
        try:
            row = connection.execute("PRAGMA integrity_check").fetchone()
            if row is None or row[0] != "ok":
                raise BackupVerificationError("La copia SQLite no supera integrity_check.")
        finally:
            connection.close()

    @staticmethod
    def _sha256_path(path):
        digest = hashlib.sha256()
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _unlink(path):
        try: Path(path).unlink(missing_ok=True)
        except OSError: pass

    @staticmethod
    def _remove_tree(path):
        for child in sorted(Path(path).rglob("*"), reverse=True):
            try:
                child.unlink() if child.is_file() or child.is_symlink() else child.rmdir()
            except OSError:
                pass
        try: Path(path).rmdir()
        except OSError: pass

    @staticmethod
    def _atomic_replace(source, destination):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        staged = destination.with_name(f".{destination.name}.{secrets.token_hex(4)}.restore")
        try:
            os.replace(source, staged)
            os.replace(staged, destination)
        except OSError as error:
            try: staged.unlink(missing_ok=True)
            except OSError: pass
            raise RestoreError("No se pudo reemplazar el archivo restaurado atomicamente.") from error

    @staticmethod
    def _iso(value):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _duration_ms(started):
        return max(0, int((datetime.now(timezone.utc) - started).total_seconds() * 1000))

    @staticmethod
    def _current_schema():
        return MIGRATIONS[-1][0]

    @staticmethod
    def _database_schema(path):
        connection = sqlite3.connect(path)
        try:
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
            if tables is None:
                return None
            row = connection.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1").fetchone()
            return row[0] if row else None
        finally:
            connection.close()

    @staticmethod
    def _migrate_path(path):
        from sqlalchemy import create_engine
        engine = create_engine(f"sqlite:///{Path(path).as_posix()}")
        try: run_migrations(engine)
        finally: engine.dispose()

    @staticmethod
    def _cancelled(token):
        return bool(token is not None and hasattr(token, "is_cancelled") and token.is_cancelled())

    def _check_cancel(self, request):
        if self._cancelled(request.cancellation_token):
            raise _Cancelled()

    def _event(self, event_name, backup_id, request, **context):
        context = {key: value for key, value in context.items() if value is not None}
        if request is not None:
            context["reason"] = request.reason
            if request.operation_id:
                context["operation_id"] = request.operation_id
        self._logger.info("Backup operation", extra={"event_name": event_name, "component": "backup", "operation_id": context.pop("operation_id", None), "context": {"backup_id": backup_id, **context}})


class _Cancelled(Exception):
    pass
