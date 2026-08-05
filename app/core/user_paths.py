"""Canonical writable paths and conservative legacy SQLite migration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import sqlite3
import tempfile


USER_DATA_ENV = "DJPLUS_USER_DATA_DIR"
_LOGGER = logging.getLogger("djplus.paths")


class UserDataPathError(RuntimeError):
    """A writable application-data location could not be prepared safely."""


class LegacyDatabaseMigrationError(UserDataPathError):
    """The legacy database was retained but could not be copied safely."""


@dataclass(frozen=True)
class UserDataPaths:
    root: Path
    database: Path
    config: Path
    logs: Path
    backups: Path

    def ensure_directories(self) -> None:
        try:
            for directory in (self.root, self.database.parent, self.config.parent, self.logs, self.backups):
                directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise UserDataPathError("No se pudo preparar el directorio de datos de DJPlus.") from error


def get_user_data_paths(environ=None, platform_name=None, home=None) -> UserDataPaths:
    """Resolve mutable paths without depending on the installation directory."""
    environ = os.environ if environ is None else environ
    platform_name = os.name if platform_name is None else platform_name
    home = Path.home() if home is None else Path(home)
    override = environ.get(USER_DATA_ENV)
    if override:
        root = Path(override).expanduser()
    elif platform_name == "nt":
        root = Path(environ.get("LOCALAPPDATA") or environ.get("APPDATA") or home / "AppData" / "Local") / "DJPlus"
    else:
        root = Path(environ.get("XDG_DATA_HOME") or home / ".local" / "share") / "DJPlus"
    root = root.expanduser()
    return UserDataPaths(root, root / "data" / "djplus.db", root / "config.json", root / "logs", root / "backups")


def _validate_sqlite(path: Path) -> None:
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise LegacyDatabaseMigrationError("No se pudo validar la integridad de la base legacy.") from error
    if result != ("ok",):
        raise LegacyDatabaseMigrationError("La base legacy no superó la validación de integridad.")


def _sqlite_backup(source: Path, destination: Path) -> None:
    try:
        input_connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        output_connection = sqlite3.connect(destination)
        try:
            input_connection.backup(output_connection)
        finally:
            output_connection.close()
            input_connection.close()
    except sqlite3.Error as error:
        raise LegacyDatabaseMigrationError("No se pudo copiar la base legacy mediante SQLite Backup API.") from error


def migrate_legacy_database(legacy_path, destination_path, copy_func=None) -> bool:
    """Safely copy a legacy database once; source and existing destination are untouched."""
    legacy, destination = Path(legacy_path), Path(destination_path)
    if destination.exists() or not legacy.is_file():
        return False
    _validate_sqlite(legacy)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".migrating", dir=destination.parent)
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            if copy_func is None:
                _sqlite_backup(legacy, temporary)
            else:
                copy_func(legacy, temporary)
            _validate_sqlite(temporary)
            if destination.exists():
                return False
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
    except LegacyDatabaseMigrationError:
        raise
    except OSError as error:
        raise LegacyDatabaseMigrationError("No se pudo copiar la base legacy sin alterar el original.") from error
    _LOGGER.info("Legacy database copied to user data", extra={"event_name": "legacy_database_copied", "component": "paths"})
    return True
