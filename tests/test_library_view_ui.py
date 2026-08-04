import unittest
from types import SimpleNamespace

from app.ui.library_view import LibraryView
from qt_test_helpers import ensure_qapplication


def _track(identifier, title="Track", artist="Artist", filepath="music.mp3"):
    return SimpleNamespace(
        id=identifier,
        title=title,
        artist=artist,
        album="Album",
        bpm=124,
        key="8A",
        duration=180,
        rating=4,
        filepath=filepath,
    )


class _Library:
    def __init__(self, rows=(_track(1),), more_rows=(_track(2, title="Next"),)):
        self.rows = tuple(rows)
        self.more_rows = tuple(more_rows)
        self.calls = []
        self.fail_refresh = False
        self.closed = False

    def load_library(self):
        self.calls.append(("load_library",))
        return list(self.rows), bool(self.more_rows)

    def load_more(self):
        self.calls.append(("load_more",))
        rows, self.more_rows = self.more_rows, ()
        return list(rows), False

    def search(self, text):
        self.calls.append(("search", text))
        return ([], False) if text == "missing" else (list(self.rows), bool(self.more_rows))

    def query(self, text="", **filters):
        self.calls.append(("query", text, filters))
        return ([], False) if text == "missing" else (list(self.rows), bool(self.more_rows))

    def sort(self, column, direction):
        self.calls.append(("sort", column, direction))
        return list(self.rows), bool(self.more_rows)

    def refresh(self):
        self.calls.append(("refresh",))
        if self.fail_refresh:
            raise RuntimeError("offline")
        return list(self.rows), bool(self.more_rows)

    def count_results(self):
        return len(self.rows) + len(self.more_rows)

    def close(self):
        self.closed = True


class _History:
    def __init__(self):
        self.selected = []
        self.closed = False

    def record_track_selected(self, track_id):
        self.selected.append(track_id)

    def close(self):
        self.closed = True


class LibraryViewUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = ensure_qapplication()

    def setUp(self):
        self.library = _Library()
        self.history = _History()
        self.view = LibraryView(self.library, self.history)

    def tearDown(self):
        self.view.close()
        self.application.processEvents()

    def test_toolbar_search_filters_and_clear_use_existing_library_contract(self):
        self.assertFalse(self.view.filter_panel.isVisible())
        self.view.filter_toggle_button.click()
        self.assertFalse(self.view.filter_panel.isHidden())

        self.view.search.setText("artist")
        self.assertEqual(self.library.calls[-1], ("search", "artist"))

        self.view.genre_filter.setText("house")
        self.view.bpm_min_filter.setValue(120)
        self.view.key_filter.setText("8A")
        self.view.rating_filter.setValue(4)
        self.view.apply_filters()
        self.assertEqual(
            self.library.calls[-1],
            ("query", "artist", {"genre": "house", "bpm_min": 120.0, "key": "8A", "rating_min": 4}),
        )

        self.view.clear_filters()
        self.assertEqual(self.library.calls[-1], ("query", "artist", {}))
        self.assertEqual(self.view._active_filters, {})

    def test_visual_states_cover_empty_no_results_and_error(self):
        empty = LibraryView(_Library(rows=(), more_rows=()), _History())
        try:
            self.assertEqual(empty.state_title.text(), "Biblioteca vacía")
            empty.search.setText("missing")
            self.assertEqual(empty.state_title.text(), "Sin resultados")
            empty.library_service.fail_refresh = True
            empty.refresh_tracks()
            self.assertEqual(empty.state_title.text(), "No se pudo cargar la biblioteca")
        finally:
            empty.close()

    def test_sort_and_incremental_loading_keep_existing_model_contract(self):
        self.view.sort_tracks(1)
        self.assertEqual(self.library.calls[-1][0:2], ("sort", "title"))
        self.assertTrue(self.view.model.canFetchMore())
        self.view.model.fetchMore()
        self.assertEqual(self.library.calls[-1], ("load_more",))
        self.assertEqual(self.view.model.rowCount(), 2)
        self.assertIn("2 de 2", self.view.counter.text())

    def test_selection_and_preview_emit_the_existing_track_without_autoplay(self):
        emitted = []
        self.view.preview_track_requested.connect(emitted.append)
        self.view.set_preview_player_available(True)
        self.view.table.setCurrentIndex(self.view.model.index(0, 0))
        self.application.processEvents()

        self.assertEqual(self.history.selected, [1])
        self.assertTrue(self.view.load_preview_button.isEnabled())
        self.view.request_preview_load()
        self.assertEqual(emitted, [self.library.rows[0]])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
