"""Manual reproducible 10k global-ranking benchmark; not part of unittest.

Creates a temporary SQLite database and removes it on exit.  The measured path
uses the real repository/library source and records the bounded top-K service.
"""

import random
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The legacy repository imports a lightweight service utility through the
# services package; initialize that package before importing the repository.
import app.services

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Track
from app.repository.track_repository import TrackRepository
from app.services.dj_intelligence_service import DJIntelligenceService
from app.services.global_ranking_factory import create_global_recommendation_facade
from app.services.global_ranking_service import GlobalRankingRequestDTO
from app.services.library_service import LibraryService


class History:
    def list_history(self, track_id=None, event_type=None, limit=None): return ()
    def count_history(self, track_id=None, event_type=None): return 0


def main():
    random.seed(19)
    with tempfile.TemporaryDirectory(prefix="djplus-global-ranking-") as directory:
        database_path = Path(directory) / "ranking.sqlite"
        setup_started = time.perf_counter()
        engine = create_engine(f"sqlite:///{database_path}")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        rows = [Track(id=1, title="origin", artist="benchmark", filepath="origin.mp3", bpm=124, key="8A", energy=70)]
        rows.extend(
            Track(id=index, title="x", artist="benchmark", filepath=f"{index}.mp3",
                  bpm=random.randint(100, 145), key="1A", energy=random.randint(1, 100))
            for index in range(2, 10001)
        )
        # id=10000 is deliberately outside the first page and first 250-row lot.
        rows[-1].bpm, rows[-1].key, rows[-1].energy = 124, "8A", 70
        session.add_all(rows)
        session.commit()
        setup_seconds = time.perf_counter() - setup_started

        statements = []
        event.listen(engine, "before_cursor_execute", lambda *_args: statements.append(1))
        library = LibraryService(TrackRepository(session=session))
        facade = create_global_recommendation_facade(library, History(), DJIntelligenceService())
        current = session.get(Track, 1)
        request = GlobalRankingRequestDTO(current, limit=50, batch_size=250)

        tracemalloc.start()
        started = time.perf_counter()
        first = facade._global_ranking_service.rank(request)
        ranking_seconds = time.perf_counter() - started
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        query_count = len(statements)
        second = facade._global_ranking_service.rank(request)
        print({
            "fixture_setup_s": round(setup_seconds, 3),
            "ranking_s": round(ranking_seconds, 3),
            "batch_size": request.batch_size,
            "k": request.limit,
            "candidates_processed": first.stats.processed,
            "candidates_per_second": round(first.stats.processed / ranking_seconds, 1),
            "queries": query_count,
            "batches": first.stats.batches,
            "peak_python_bytes": peak,
            "best_track_id": first.recommendations[0].candidate_track_id,
            "deterministic": first.recommendations == second.recommendations,
        })
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
