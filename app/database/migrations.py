"""Small, ordered, idempotent SQLite schema migration runner."""

from sqlalchemy import inspect, text

from .models import Base


MIGRATIONS = (
    ("0001_baseline_schema", "Create the v0.5 baseline schema", "_baseline_schema"),
)


def run_migrations(engine):
    """Bring a new or existing DJPlus SQLite database to the current schema."""
    _create_migration_table(engine)
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        applied = {
            row[0]
            for row in connection.execute(text("SELECT version FROM schema_migrations"))
        }

    for version, _, function_name in MIGRATIONS:
        if version in applied:
            continue
        with engine.begin() as connection:
            globals()[function_name](connection)
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": version},
            )


def _create_migration_table(engine):
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version VARCHAR(64) PRIMARY KEY NOT NULL, "
                "applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
        )


def _baseline_schema(connection):
    columns = {
        column["name"]
        for column in inspect(connection).get_columns("tracks")
    }
    missing_columns = {
        "file_hash": "VARCHAR",
        "status": "VARCHAR DEFAULT 'ok'",
        "is_favorite": "BOOLEAN NOT NULL DEFAULT 0",
    }
    for name, definition in missing_columns.items():
        if name not in columns:
            connection.execute(text(f"ALTER TABLE tracks ADD COLUMN {name} {definition}"))

    indexes = (
        "CREATE INDEX IF NOT EXISTS ix_collection_tracks_track_id ON collection_tracks (track_id)",
        "CREATE INDEX IF NOT EXISTS ix_collection_rules_collection_id ON collection_rules (collection_id)",
        "CREATE INDEX IF NOT EXISTS ix_playlist_tracks_track_id ON playlist_tracks (track_id)",
        "CREATE INDEX IF NOT EXISTS ix_track_history_track_created_at ON track_history (track_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_track_history_event_created_at ON track_history (event_type, created_at)",
    )
    for statement in indexes:
        connection.execute(text(statement))
