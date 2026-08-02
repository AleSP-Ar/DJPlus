import unittest

from sqlalchemy import create_engine, inspect, text

from app.database.migrations import run_migrations


class MigrationTests(unittest.TestCase):
    def test_migrations_create_current_schema_and_are_idempotent(self):
        engine = create_engine("sqlite:///:memory:")
        run_migrations(engine)
        run_migrations(engine)

        inspector = inspect(engine)
        self.assertTrue({"tracks", "collections", "playlists", "track_history", "collection_rules"}.issubset(inspector.get_table_names()))
        self.assertIn("is_favorite", {column["name"] for column in inspector.get_columns("tracks")})
        with engine.connect() as connection:
            versions = connection.execute(text("SELECT version FROM schema_migrations")).scalars().all()
        self.assertEqual(versions, ["0001_baseline_schema"])

    def test_migrations_upgrade_a_legacy_tracks_table(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE tracks (id INTEGER PRIMARY KEY, title VARCHAR NOT NULL, "
                    "artist VARCHAR NOT NULL, filepath VARCHAR NOT NULL UNIQUE)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO tracks (id, title, artist, filepath) "
                    "VALUES (1, 'Existing track', 'DJ Plus', 'existing.mp3')"
                )
            )
        run_migrations(engine)
        columns = {column["name"] for column in inspect(engine).get_columns("tracks")}
        self.assertTrue({"file_hash", "status", "is_favorite"}.issubset(columns))
        with engine.connect() as connection:
            track = connection.execute(
                text("SELECT title, artist, filepath, is_favorite FROM tracks WHERE id = 1")
            ).one()
        self.assertEqual(track, ("Existing track", "DJ Plus", "existing.mp3", 0))
