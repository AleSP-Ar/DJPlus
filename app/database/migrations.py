"""Small, ordered, idempotent SQLite schema migration runner."""

from sqlalchemy import inspect, text

MIGRATIONS = (
    ("0001_baseline_schema", "Create the v0.5 baseline schema", "_baseline_schema"),
    ("0002_import_engine", "Create persistent import jobs and items", "_import_engine"),
    ("0003_track_import_snapshots", "Add track import metadata and snapshots", "_track_import_snapshots"),
)


def run_migrations(engine):
    """Bring a new or existing DJPlus SQLite database to the current schema."""
    _create_migration_table(engine)
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
    statements = (
        "CREATE TABLE IF NOT EXISTS tracks ("
        "id INTEGER PRIMARY KEY, title VARCHAR NOT NULL, artist VARCHAR NOT NULL, album VARCHAR, "
        "filepath VARCHAR NOT NULL UNIQUE, bpm FLOAT, key VARCHAR, duration FLOAT, file_hash VARCHAR, "
        "status VARCHAR DEFAULT 'ok', energy INTEGER DEFAULT 0, rating INTEGER DEFAULT 0, "
        "is_favorite BOOLEAN NOT NULL DEFAULT 0, created_at DATETIME)",
        "CREATE TABLE IF NOT EXISTS collections ("
        "id INTEGER PRIMARY KEY, name VARCHAR(120) COLLATE NOCASE NOT NULL UNIQUE, description VARCHAR, "
        "color VARCHAR(32), icon VARCHAR(64), type VARCHAR(16) NOT NULL DEFAULT 'manual' "
        "CHECK (type IN ('manual', 'smart')), created_at DATETIME, updated_at DATETIME)",
        "CREATE TABLE IF NOT EXISTS collection_tracks ("
        "collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE, "
        "track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE, "
        "PRIMARY KEY (collection_id, track_id))",
        "CREATE TABLE IF NOT EXISTS playlists ("
        "id INTEGER PRIMARY KEY, name VARCHAR(120) COLLATE NOCASE NOT NULL UNIQUE, description VARCHAR, "
        "created_at DATETIME, updated_at DATETIME)",
        "CREATE TABLE IF NOT EXISTS playlist_tracks ("
        "id INTEGER PRIMARY KEY, playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE, "
        "track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE, position INTEGER NOT NULL "
        "CHECK (position >= 0), added_at DATETIME, "
        "CONSTRAINT uq_playlist_tracks_playlist_track UNIQUE (playlist_id, track_id), "
        "CONSTRAINT uq_playlist_tracks_playlist_position UNIQUE (playlist_id, position))",
        "CREATE TABLE IF NOT EXISTS track_history ("
        "id INTEGER PRIMARY KEY, track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE, "
        "event_type VARCHAR(32) NOT NULL CHECK (event_type IN ('selected', 'played', 'added', 'playlist_used')), "
        "created_at DATETIME)",
        "CREATE TABLE IF NOT EXISTS collection_rules ("
        "id INTEGER PRIMARY KEY, collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE, "
        "field VARCHAR(64) NOT NULL, operator VARCHAR(16) NOT NULL, value VARCHAR NOT NULL, created_at DATETIME)",
    )
    for statement in statements:
        connection.execute(text(statement))
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


def _import_engine(connection):
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS import_jobs ("
            "id INTEGER PRIMARY KEY, "
            "status VARCHAR(32) NOT NULL DEFAULT 'pending' "
            "CHECK (status IN ('pending', 'scanning', 'reading_metadata', 'imported', "
            "'skipped', 'failed', 'cancelled')), "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "started_at DATETIME, "
            "finished_at DATETIME, "
            "total_items INTEGER NOT NULL DEFAULT 0, "
            "processed_items INTEGER NOT NULL DEFAULT 0, "
            "error_count INTEGER NOT NULL DEFAULT 0"
            ")"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS import_items ("
            "id INTEGER PRIMARY KEY, "
            "job_id INTEGER NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE, "
            "filepath VARCHAR NOT NULL, "
            "status VARCHAR(32) NOT NULL DEFAULT 'pending' "
            "CHECK (status IN ('pending', 'scanning', 'reading_metadata', 'imported', "
            "'skipped', 'failed', 'cancelled')), "
            "error_message VARCHAR, "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "CONSTRAINT uq_import_items_job_filepath UNIQUE (job_id, filepath)"
            ")"
        )
    )
    indexes = (
        "CREATE INDEX IF NOT EXISTS ix_import_jobs_status ON import_jobs (status)",
        "CREATE INDEX IF NOT EXISTS ix_import_items_job_status ON import_items (job_id, status)",
    )
    for statement in indexes:
        connection.execute(text(statement))


def _track_import_snapshots(connection):
    columns = {
        column["name"]
        for column in inspect(connection).get_columns("tracks")
    }
    missing_columns = {
        "genre": "VARCHAR",
        "bitrate": "INTEGER",
        "sample_rate": "INTEGER",
        "import_file_size": "INTEGER",
        "import_file_modified_at": "DATETIME",
    }
    for name, definition in missing_columns.items():
        if name not in columns:
            connection.execute(text(f"ALTER TABLE tracks ADD COLUMN {name} {definition}"))
