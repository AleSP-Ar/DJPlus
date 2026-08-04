"""Reproducible SQLite migration benchmark; intentionally outside unittest."""

import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text

from app.database.migrations import _baseline_schema, run_migrations


def benchmark(count=1000):
    with tempfile.TemporaryDirectory(prefix="djplus-migration-") as directory:
        path = Path(directory) / "historical.sqlite"
        engine = create_engine(f"sqlite:///{path.as_posix()}")
        started = time.perf_counter()
        with engine.begin() as connection:
            _baseline_schema(connection)
            connection.execute(text("CREATE TABLE schema_migrations (version VARCHAR(64) PRIMARY KEY NOT NULL)"))
            connection.execute(text("INSERT INTO schema_migrations (version) VALUES ('0001_baseline_schema')"))
            connection.execute(text("INSERT INTO tracks (id,title,artist,filepath) VALUES (:id,'fixture','benchmark',:path)"), [{"id": index, "path": f"{index}.wav"} for index in range(1, count + 1)])
        fixture_seconds = time.perf_counter() - started
        tracemalloc.start(); started = time.perf_counter(); run_migrations(engine); migration_seconds = time.perf_counter() - started
        _current, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
        with engine.connect() as connection:
            integrity = connection.execute(text("PRAGMA integrity_check")).scalar_one()
            foreign_keys = connection.execute(text("PRAGMA foreign_key_check")).fetchall()
        engine.dispose()
        return {"tracks": count, "fixture_s": round(fixture_seconds, 3), "migration_s": round(migration_seconds, 3), "peak_python_bytes": peak, "integrity": integrity, "foreign_key_rows": len(foreign_keys)}


if __name__ == "__main__":
    for size in (1000, 10000):
        print(benchmark(size))
