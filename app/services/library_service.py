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

    def load_page(self, page_number):
        """Load one numbered page using the current search, filters and order."""
        if not isinstance(page_number, int) or page_number < 1:
            raise ValueError("El numero de pagina debe ser un entero positivo.")
        offset = (page_number - 1) * self.page_size
        rows, has_more = self._load_page(offset)
        self.offset = offset
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
        session = getattr(self.repository, "session", None)
        if session is not None and callable(getattr(session, "expire_all", None)):
            session.expire_all()
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

    def update_rating(self, track_id, rating):
        """Persist one user-selected star rating without changing audio metadata."""
        if not isinstance(track_id, int):
            raise TypeError("track_id debe ser entero.")
        if not isinstance(rating, int) or not 0 <= rating <= 5:
            raise ValueError("rating debe estar entre 0 y 5.")
        track = self.repository.get_by_id(track_id)
        if track is None:
            raise ValueError("La pista seleccionada ya no existe.")
        return self.repository.update_track_metadata(track, {"rating": rating})

    def update_metadata(self, track_id, values):
        """Persist a manual edit launched from the library without changing audio files."""
        if not isinstance(track_id, int):
            raise TypeError("track_id debe ser entero.")
        if not isinstance(values, dict):
            raise TypeError("values debe ser un diccionario.")
        allowed = {"title", "artist", "album", "label", "genre", "bpm", "key", "energy"}
        patch = {field: value for field, value in values.items() if field in allowed}
        if not patch:
            raise ValueError("No hay cambios de metadata.")
        track = self.repository.get_by_id(track_id)
        if track is None:
            raise ValueError("La pista seleccionada ya no existe.")
        previous = {field: getattr(track, field, None) for field in patch}
        self.repository.update_track_metadata(track, patch, commit=False)
        self.repository.record_metadata_edit(track_id, tuple(patch), previous, patch, "manual_library", "applied")
        return track

    def iter_ranking_candidates(self, *, batch_size, filters, excluded_track_ids, cancellation=None):
        """Global read-only source; does not alter current UI pagination state."""
        from .global_ranking_service import RankingTrackDTO
        for rows in self.repository.iter_ranking_rows(batch_size=batch_size, filters=filters, excluded_track_ids=excluded_track_ids, cancellation=cancellation):
            yield tuple(RankingTrackDTO(row.id, row.bpm, row.key, row.energy, row.rating or 0, row.genre, bool(row.is_favorite), row.duration, row.filepath) for row in rows)

    def close(self):
        self.repository.close()
