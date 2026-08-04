from app.repository.track_repository import TrackRepository

from .filter_engine import FilterEngine
from .search_engine import SearchEngine
from .sort_engine import SortEngine


class LibraryService:
    """Application service that exposes library operations to the UI."""

    def __init__(self, repository=None, page_size=200):
        self.repository = repository or TrackRepository()
        self.search_engine = SearchEngine()
        self.sort_engine = SortEngine()
        self.filter_engine = FilterEngine()
        self.search_criteria = self.search_engine.build()
        self.filter_criteria = self.filter_engine.build()
        self.sort_spec = self.sort_engine.build("artist")
        self.page_size = page_size
        self.offset = 0
        self._result_count = None

    def load_library(self):
        self.offset = 0
        rows, has_more = self._load_page()
        self._result_count = self.repository.count_query_tracks(
            self.search_criteria,
            self.filter_criteria,
        )
        return rows, has_more

    def load_more(self):
        next_offset = self.offset + self.page_size
        rows, has_more = self._load_page(next_offset)
        if rows:
            self.offset = next_offset
        return rows, has_more

    def _load_page(self, offset=None):
        if offset is None:
            offset = self.offset
        rows = self.repository.query_tracks(
            self.search_criteria,
            self.filter_criteria,
            self.sort_spec,
            limit=self.page_size + 1,
            offset=offset,
        )
        has_more = len(rows) > self.page_size
        return rows[:self.page_size], has_more

    def search(self, text="", **fields):
        self.search_criteria = self.search_engine.build(text=text, **fields)
        return self.load_library()

    def sort(self, column, direction="asc"):
        self.sort_spec = self.sort_engine.build(column, direction)
        return self.load_library()

    def filter(self, **filters):
        self.filter_criteria = self.filter_engine.build(**filters)
        return self.load_library()

    def query(self, text="", **filters):
        """Apply validated text and filter criteria together through the service boundary."""
        self.search_criteria = self.search_engine.build(text=text)
        self.filter_criteria = self.filter_engine.build(**filters)
        return self.load_library()

    def apply_filter_criteria(self, criteria):
        """Replace active filters with validated criteria from another service."""
        self.filter_criteria = criteria
        return self.load_library()

    def refresh(self):
        return self.load_library()

    def count_tracks(self):
        return self.repository.count_tracks()

    def count_results(self):
        """Return the total matching the current search and filters."""
        if self._result_count is None:
            self._result_count = self.repository.count_query_tracks(
                self.search_criteria,
                self.filter_criteria,
            )
        return self._result_count

    def iter_ranking_candidates(self, *, batch_size, filters, excluded_track_ids, cancellation=None):
        """Global read-only source; does not alter current UI pagination state."""
        from .global_ranking_service import RankingTrackDTO
        for rows in self.repository.iter_ranking_rows(batch_size=batch_size, filters=filters, excluded_track_ids=excluded_track_ids, cancellation=cancellation):
            yield tuple(RankingTrackDTO(row.id, row.bpm, row.key, row.energy, row.rating or 0, row.genre, bool(row.is_favorite), row.duration, row.filepath) for row in rows)

    def close(self):
        self.repository.close()
