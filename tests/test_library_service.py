import unittest
from types import SimpleNamespace

from app.services.library_service import LibraryService
from app.services.filter_engine import FilterEngine
from app.services.search_engine import SearchEngine
from app.services.sort_engine import SortEngine


class FakeTrackRepository:
    def __init__(self):
        self.closed = False
        self.count_query_calls = 0

    tracks = [f"track-{index}" for index in range(450)]

    def get_all_tracks(self):
        return ["track-1", "track-2"]

    def query_tracks(self, search, filters, sort, limit=None, offset=0):
        self.query = (search, filters, sort, limit, offset)
        return self.tracks[offset:offset + limit]

    def count_tracks(self):
        return len(self.tracks)

    def count_query_tracks(self, search, filters):
        self.count_query_calls += 1
        return len(self.tracks)

    def close(self):
        self.closed = True

    def get_by_id(self, track_id):
        return SimpleNamespace(id=track_id, rating=0) if track_id == 1 else None

    def update_track_metadata(self, track, values):
        self.rating_update = (track.id, values)
        track.rating = values["rating"]
        return track


class LibraryServiceTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeTrackRepository()
        self.service = LibraryService(repository=self.repository)

    def test_load_library_delegates_to_repository(self):
        tracks, has_more = self.service.load_library()
        self.assertEqual(tracks, self.repository.tracks[:200])
        self.assertTrue(has_more)

    def test_load_more_reads_the_next_non_overlapping_page(self):
        first_page, _ = self.service.load_library()
        next_page, has_more = self.service.load_more()

        self.assertEqual(next_page, self.repository.tracks[200:400])
        self.assertTrue(has_more)
        self.assertFalse(set(first_page) & set(next_page))
        self.assertEqual(self.repository.query[4], 200)

    def test_search_and_sort_restart_pagination(self):
        self.service.load_library()
        self.service.load_more()
        self.service.search("artist")
        self.assertEqual(self.repository.query[4], 0)
        self.service.load_more()
        self.service.sort("title", "desc")
        self.assertEqual(self.repository.query[4], 0)

    def test_search_and_sort_build_a_repository_query(self):
        self.service.search("artist")
        self.service.sort("title", "desc")
        search, _, sort, _, _ = self.repository.query
        self.assertEqual(search.text, "artist")
        self.assertEqual(sort.column, "title")
        self.assertEqual(sort.direction, "desc")

    def test_count_tracks_delegates_to_repository(self):
        self.assertEqual(self.service.count_tracks(), 450)

    def test_count_results_delegates_active_criteria_to_repository(self):
        self.service.search("artist")
        self.assertEqual(self.service.count_results(), 450)
        self.assertEqual(self.repository.count_query_calls, 1)

    def test_close_delegates_to_repository(self):
        self.service.close()
        self.assertTrue(self.repository.closed)

    def test_update_rating_persists_only_the_validated_star_value(self):
        updated = self.service.update_rating(1, 5)
        self.assertEqual(updated.rating, 5)
        self.assertEqual(self.repository.rating_update, (1, {"rating": 5}))
        with self.assertRaises(ValueError):
            self.service.update_rating(1, 6)


class EngineTests(unittest.TestCase):
    def test_search_engine_preserves_supported_fields(self):
        criteria = SearchEngine().build(artist="Artist", bpm=123)
        self.assertEqual(criteria.artist, "Artist")
        self.assertEqual(criteria.bpm, 123)

    def test_sort_engine_rejects_unknown_columns(self):
        with self.assertRaises(ValueError):
            SortEngine().build("unknown")

    def test_filter_engine_rejects_invalid_ranges(self):
        with self.assertRaises(ValueError):
            FilterEngine().build(bpm_min=125, bpm_max=120)

    def test_filter_engine_preserves_genre_and_label(self):
        criteria = FilterEngine().build(genre="Progressive House", label="Lost & Found")
        self.assertEqual((criteria.genre, criteria.label), ("Progressive House", "Lost & Found"))


if __name__ == "__main__":
    unittest.main()
