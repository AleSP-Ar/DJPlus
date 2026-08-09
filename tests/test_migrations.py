import unittest
from unittest import mock

from sqlalchemy import create_engine, inspect, text

from app.database.migrations import (
    MIGRATIONS,
    MigrationFutureVersionError,
    MigrationHistoryError,
    _baseline_schema,
    run_migrations,
)


class MigrationTests(unittest.TestCase):
    def test_migrations_create_current_schema_and_are_idempotent(self):
        engine = create_engine("sqlite:///:memory:")
        run_migrations(engine)
        run_migrations(engine)

        inspector = inspect(engine)
        self.assertTrue(
            {
                "tracks",
                "collections",
                "playlists",
                "track_history",
                "collection_rules",
                "import_jobs",
                "import_items",
            }.issubset(inspector.get_table_names())
        )
        track_columns = {column["name"] for column in inspector.get_columns("tracks")}
        self.assertTrue(
            {"is_favorite", "label", "genre", "bitrate", "sample_rate", "import_file_size", "import_file_modified_at", "analyzed_at", "analyzer_version", "bpm_confidence", "key_confidence", "energy_confidence"}.issubset(
                track_columns
            )
        )
        with engine.connect() as connection:
            versions = connection.execute(text("SELECT version FROM schema_migrations")).scalars().all()
        self.assertEqual(versions, [version for version, _description, _function in MIGRATIONS])
        self.assertIn("track_metadata_history", inspector.get_table_names())
        indexes = {index["name"] for index in inspector.get_indexes("import_items")}
        self.assertIn("ix_import_items_job_status", indexes)

    def test_migrations_upgrade_a_v050_database_without_losing_data(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            _baseline_schema(connection)
            connection.execute(text("CREATE TABLE schema_migrations (version VARCHAR(64) PRIMARY KEY NOT NULL)"))
            connection.execute(text("INSERT INTO schema_migrations (version) VALUES ('0001_baseline_schema')"))
            connection.execute(
                text(
                    "INSERT INTO tracks (id, title, artist, filepath) "
                    "VALUES (1, 'Existing track', 'DJ Plus', 'existing.mp3')"
                )
            )
        run_migrations(engine)
        columns = {column["name"] for column in inspect(engine).get_columns("tracks")}
        self.assertTrue(
            {
                "file_hash",
                "status",
                "is_favorite",
                "label",
                "genre",
                "bitrate",
                "sample_rate",
                "import_file_size",
                "import_file_modified_at",
                "analyzed_at",
                "analyzer_version",
                "bpm_confidence",
                "key_confidence",
                "energy_confidence",
            }.issubset(columns)
        )
        with engine.connect() as connection:
            track = connection.execute(
                text("SELECT title, artist, filepath, is_favorite FROM tracks WHERE id = 1")
            ).one()
        self.assertEqual(track, ("Existing track", "DJ Plus", "existing.mp3", 0))
        with engine.connect() as connection:
            versions = connection.execute(text("SELECT version FROM schema_migrations")).scalars().all()
        self.assertEqual(versions, [version for version, _description, _function in MIGRATIONS])

    def test_each_supported_historical_prefix_upgrades_idempotently(self):
        for count in range(1, len(MIGRATIONS) + 1):
            with self.subTest(count=count):
                engine = create_engine("sqlite:///:memory:")
                with engine.begin() as connection:
                    connection.execute(text("CREATE TABLE schema_migrations (version VARCHAR(64) PRIMARY KEY NOT NULL)"))
                    for version, _description, function_name in MIGRATIONS[:count]:
                        globals_module = __import__("app.database.migrations", fromlist=[function_name])
                        getattr(globals_module, function_name)(connection)
                        connection.execute(text("INSERT INTO schema_migrations (version) VALUES (:version)"), {"version": version})
                    connection.execute(text("INSERT INTO tracks (id, title, artist, filepath, is_favorite) VALUES (1, 'fixture', 'test', 'fixture.wav', 1)"))
                run_migrations(engine)
                run_migrations(engine)
                with engine.connect() as connection:
                    self.assertEqual(connection.execute(text("SELECT count(*) FROM tracks")).scalar_one(), 1)
                    self.assertEqual(connection.execute(text("SELECT count(*) FROM schema_migrations")).scalar_one(), len(MIGRATIONS))

    def test_future_and_inconsistent_history_are_rejected_without_repair(self):
        future = create_engine("sqlite:///:memory:")
        with future.begin() as connection:
            connection.execute(text("CREATE TABLE schema_migrations (version VARCHAR(64) PRIMARY KEY NOT NULL)"))
            connection.execute(text("INSERT INTO schema_migrations (version) VALUES ('0006_future')"))
        with self.assertRaises(MigrationFutureVersionError):
            run_migrations(future)

        inconsistent = create_engine("sqlite:///:memory:")
        with inconsistent.begin() as connection:
            connection.execute(text("CREATE TABLE schema_migrations (version VARCHAR(64) PRIMARY KEY NOT NULL)"))
            connection.execute(text("INSERT INTO schema_migrations (version) VALUES ('0002_import_engine')"))
        with self.assertRaises(MigrationHistoryError):
            run_migrations(inconsistent)

    def test_nonempty_database_without_history_is_rejected(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE external_data (id INTEGER PRIMARY KEY)"))
        with self.assertRaises(MigrationHistoryError):
            run_migrations(engine)

    def test_failure_after_ddl_or_index_does_not_record_partial_migration(self):
        """SQLite may retain DDL, but history is written only after migration success."""
        import app.database.migrations as migrations

        engine = create_engine("sqlite:///:memory:")
        original = migrations._import_engine

        def fail_after_ddl_and_indexes(connection):
            original(connection)
            raise RuntimeError("injected ddl/index failure")

        with mock.patch.object(migrations, "_import_engine", side_effect=fail_after_ddl_and_indexes):
            with self.assertRaisesRegex(RuntimeError, "injected ddl/index failure"):
                run_migrations(engine)
        with engine.connect() as connection:
            versions = connection.execute(text("SELECT version FROM schema_migrations")).scalars().all()
        self.assertEqual(versions, ["0001_baseline_schema"])

        # Re-entry is safe even if SQLite retained idempotent DDL from the failed attempt.
        run_migrations(engine)
        with engine.connect() as connection:
            versions = connection.execute(text("SELECT version FROM schema_migrations")).scalars().all()
        self.assertEqual(versions, [version for version, _description, _function in MIGRATIONS])
