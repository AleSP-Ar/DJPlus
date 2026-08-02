"""Profile the isolated Import Engine without touching the application database.

Example: .\\.venv\\Scripts\\python.exe tools/benchmarks/benchmark_import_engine.py --files 100
Use --measure-memory only for a separate memory-focused pass; tracemalloc changes timings.
"""

import argparse
import json
import sys
import tempfile
import time
import tracemalloc
import wave
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.migrations import run_migrations
from app.database.unit_of_work import UnitOfWork
from app.repository.import_repository import ImportRepository
from app.services.import_queue import ImportQueue
from app.services.import_service import ImportService
from app.services.metadata_service import MetadataService
from app.services.scanner_service import ScannerService
from app.services.track_import_service import TrackImportService


class Timings:
    def __init__(self):
        self.values = defaultdict(float)
        self.counts = defaultdict(int)

    def measure(self, name, callback, *args, **kwargs):
        started_at = time.perf_counter()
        try:
            return callback(*args, **kwargs)
        finally:
            self.values[name] += time.perf_counter() - started_at
            self.counts[name] += 1

    def report(self):
        return {
            name: {
                "seconds": round(seconds, 6),
                "calls": self.counts[name],
                "milliseconds_per_call": round(seconds * 1000 / self.counts[name], 3),
            }
            for name, seconds in sorted(self.values.items())
        }


class TimedScanner:
    def __init__(self, scanner, timings):
        self.scanner = scanner
        self.timings = timings

    def discover(self, *args, **kwargs):
        iterator = self.scanner.discover(*args, **kwargs)
        while True:
            try:
                event = self.timings.measure("scanner", next, iterator)
            except StopIteration:
                return
            yield event


class TimedMetadata:
    def __init__(self, metadata_service, timings):
        self.metadata_service = metadata_service
        self.timings = timings

    def read(self, filepath):
        return self.timings.measure("metadata", self.metadata_service.read, filepath)


class TimedQueue:
    def __init__(self, queue, timings):
        self.queue = queue
        self.timings = timings

    def __getattr__(self, name):
        attribute = getattr(self.queue, name)
        if not callable(attribute):
            return attribute
        return lambda *args, **kwargs: self.timings.measure("import_queue", attribute, *args, **kwargs)


class TimedTrackImport:
    def __init__(self, service, timings):
        self.service = service
        self.timings = timings

    def process(self, item_id, metadata):
        return self.timings.measure("track_import", self.service.process, item_id, metadata)


class TimedUnitOfWork(UnitOfWork):
    def __init__(self, session_factory, timings):
        super().__init__(session_factory=session_factory)
        self.timings = timings

    def __enter__(self):
        return self.timings.measure("unit_of_work_open", super().__enter__)

    def commit(self):
        return self.timings.measure("sqlite_commit_track", super().commit)


def write_wav(filepath):
    with wave.open(str(filepath), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(44100)
        audio.writeframes(b"\\x00\\x00" * 4410)


def main():
    parser = argparse.ArgumentParser(description="Perfil aislado del Import Engine")
    parser.add_argument("--files", type=int, default=100, help="Cantidad de WAV válidos a importar")
    parser.add_argument("--measure-memory", action="store_true", help="Mide pico Python con tracemalloc")
    arguments = parser.parse_args()
    if arguments.files < 1:
        parser.error("--files debe ser mayor que cero")

    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        for index in range(arguments.files):
            write_wav(root / f"track-{index:05d}.wav")
        (root / "invalid.mp3").write_bytes(b"not audio")

        engine = create_engine(f"sqlite:///{(root / 'benchmark.db').as_posix()}")
        run_migrations(engine)
        session_factory = sessionmaker(bind=engine)
        repository = ImportRepository(session=session_factory())
        timings = Timings()
        repository_commit = repository.session.commit
        repository.session.commit = lambda: timings.measure("sqlite_commit_queue", repository_commit)
        track_import = TrackImportService(
            unit_of_work_factory=lambda: TimedUnitOfWork(session_factory, timings)
        )
        service = ImportService(
            scanner_service=TimedScanner(ScannerService(), timings),
            metadata_service=TimedMetadata(MetadataService(), timings),
            queue=TimedQueue(ImportQueue(repository), timings),
            track_import_service=TimedTrackImport(track_import, timings),
        )

        if arguments.measure_memory:
            tracemalloc.start()
        started_at = time.perf_counter()
        job = service.run(root)
        elapsed_seconds = time.perf_counter() - started_at
        peak_bytes = tracemalloc.get_traced_memory()[1] if arguments.measure_memory else None
        if arguments.measure_memory:
            tracemalloc.stop()
        result = repository.get_progress(job.id)
        repository.close()
        engine.dispose()

    print(json.dumps({
        "audio_files": arguments.files,
        "total_items": result["total_items"],
        "processed_items": result["processed_items"],
        "errors": result["error_count"],
        "job_status": result["status"],
        "elapsed_seconds": round(elapsed_seconds, 3),
        "peak_memory_mib": round(peak_bytes / (1024 * 1024), 3) if peak_bytes is not None else None,
        "timings": timings.report(),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
