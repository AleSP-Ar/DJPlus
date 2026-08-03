import unittest

from sqlalchemy import create_engine, inspect, text

from app.database.migrations import _baseline_schema, run_migrations


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
            {"is_favorite", "genre", "bitrate", "sample_rate", "import_file_size", "import_file_modified_at", "analyzed_at", "analyzer_version", "bpm_confidence", "key_confidence", "energy_confidence"}.issubset(
                track_columns
            )
        )
        with engine.connect() as connection:
            versions = connection.execute(text("SELECT version FROM schema_migrations")).scalars().all()
        self.assertEqual(versions, ["0001_baseline_schema", "0002_import_engine", "0003_track_import_snapshots", "0004_analysis_provenance", "0005_track_metadata_history"])
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
        self.assertEqual(versions, ["0001_baseline_schema", "0002_import_engine", "0003_track_import_snapshots", "0004_analysis_provenance", "0005_track_metadata_history"])
