from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.core.user_paths import get_user_data_paths, migrate_legacy_database

try:
    from .migrations import run_migrations
except ImportError:  # pragma: no cover - fallback for direct execution
    from migrations import run_migrations


PROJECT_ROOT = Path(__file__).resolve().parents[2]
USER_DATA_PATHS = get_user_data_paths()
DATABASE_PATH = USER_DATA_PATHS.database
LEGACY_DATABASE_PATH = PROJECT_ROOT / "data" / "djplus.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"timeout": 30},
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(connection, _):
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")

SessionLocal = sessionmaker(bind=engine)
_LOGGER = logging.getLogger("djplus.database")


def init_database() -> None:
    # Directory creation belongs to explicit startup, never module import.
    USER_DATA_PATHS.ensure_directories()
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    migrate_legacy_database(LEGACY_DATABASE_PATH, DATABASE_PATH)
    # SQLite allows one writer at a time.  WAL keeps readers responsive while
    # imports, playback history and the assistant use separate sessions.
    # It must be configured once at startup, rather than on every connection.
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        connection.exec_driver_sql("PRAGMA synchronous=NORMAL")
        connection.exec_driver_sql("PRAGMA busy_timeout=30000")
    _LOGGER.info(
        "Database migration started",
        extra={"event_name": "database_migration_started", "component": "database"},
    )
    run_migrations(engine)
    _LOGGER.info(
        "Database migration completed",
        extra={"event_name": "database_migration_completed", "component": "database"},
    )


def init_db() -> None:
    init_database()


def create_backup_restore_service(settings_service, logging_service=None):
    """Compose the backup boundary with the canonical database lifecycle."""
    from app.services.backup_restore_service import BackupRestoreService

    logger = logging_service.get_logger("backup") if logging_service is not None else logging.getLogger("djplus.backup")
    return BackupRestoreService(settings_service, DATABASE_PATH, logger=logger, close_connections=engine.dispose)
