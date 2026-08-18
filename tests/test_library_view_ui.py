import unittest
from types import SimpleNamespace

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from app.ui.library_view import LibraryView
from qt_test_helpers import ensure_qapplication


def _track(identifier, title="Track", artist="Artist", filepath="music.mp3"):
    return SimpleNamespace(
        id=identifier,
        title=title,
        artist=artist,
        album="Album",
        label="Demo Label",
        bpm=124,
        key="8A",
        duration=180,
        rating=4,
        genre="House",
        secondary_genres_json='[["deep_house", "Deep House", 0.8]]',
        styles_json='[["deep", "Deep", 0.75]]',
        energy=80,
        filepath=filepath,
    )


class _Library:
    def __init__(self, rows=(_track(1),), more_rows=(_track(2, title="Next"),)):
        self.rows = tuple(rows)
        self.more_rows = tuple(more_rows)
        self.calls = []
        self.fail_refresh = False
        self.closed = False
        self.rating_updates = []

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

    def update_rating(self, track_id, rating):
        self.rating_updates.append((track_id, rating))
        track = next(track for track in self.rows if track.id == track_id)
        track.rating = rating
        return track

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
        QTest.qWait(300)
        self.assertEqual(self.library.calls[-1], ("search", "artist"))

        self.view.genre_filter.setText("house")
        self.view.label_filter.setText("demo")
        self.view.bpm_min_filter.setValue(120)
        self.view.key_filter.setText("8A")
        self.view.rating_filter.setValue(4)
        self.view.apply_filters()
        self.assertEqual(
            self.library.calls[-1],
            ("query", "artist", {"genre": "house", "label": "demo", "bpm_min": 120.0, "key": "8A", "rating_min": 4}),
        )

        self.view.clear_filters()
        self.assertEqual(self.library.calls[-1], ("query", "", {}))
        self.assertEqual(self.view.search.text(), "")
        self.assertEqual(self.view._active_filters, {})

    def test_visual_states_cover_empty_no_results_and_error(self):
        empty = LibraryView(_Library(rows=(), more_rows=()), _History())
        try:
            self.assertEqual(empty.state_title.text(), "Biblioteca vacía")
            empty.search.setText("missing")
            QTest.qWait(300)
            self.assertEqual(empty.state_title.text(), "Sin resultados")
            empty.library_service.fail_refresh = True
            empty.refresh_tracks()
            self.assertEqual(empty.state_title.text(), "No se pudo cargar la biblioteca")
        finally:
            empty.close()

    def test_sort_and_incremental_loading_keep_existing_model_contract(self):
        self.view.sort_tracks(2)
        self.assertEqual(self.library.calls[-1][0:2], ("sort", "title"))
        self.assertTrue(self.view.model.canFetchMore())
        self.view.model.fetchMore()
        self.assertEqual(self.library.calls[-1], ("load_more",))
        self.assertEqual(self.view.model.rowCount(), 2)
        self.assertIn("2 de 2", self.view.counter.text())

    def test_library_shows_genre_and_label_without_style_columns_and_updates_rating(self):
        headers = self.view.model.HEADERS
        self.assertIn("Género", headers)
        self.assertNotIn("Géneros secundarios", headers)
        self.assertNotIn("Estilos", headers)
        self.assertIn("Sello", headers)
        self.assertEqual(self.view.model.data(self.view.model.index(0, 4), Qt.DisplayRole), "Demo Label")
        self.assertEqual(self.view.model.data(self.view.model.index(0, 5), Qt.DisplayRole), "House")

        rating_index = self.view.model.index(0, 10)
        self.view.show()
        self.application.processEvents()
        self.view.table.scrollTo(rating_index)
        self.application.processEvents()
        bounds = self.view.table.visualRect(rating_index)
        stars_width = self.view.table.fontMetrics().horizontalAdvance("★★★★★")
        QTest.mouseClick(
            self.view.table.viewport(), Qt.LeftButton,
            pos=QPoint(int(bounds.center().x() + stars_width / 2 - 1), bounds.center().y()),
        )
        self.assertEqual(self.library.rating_updates, [(1, 5)])
        self.assertEqual(self.view.model.data(rating_index, Qt.DisplayRole), "★★★★★")
        self.assertEqual(self.history.selected, [])

        QTest.mouseClick(
            self.view.table.viewport(), Qt.LeftButton,
            pos=QPoint(int(bounds.center().x() + stars_width / 2 - 1), bounds.center().y()),
        )
        self.assertEqual(self.library.rating_updates[-1], (1, 0))
        self.assertTrue(self.view.table.horizontalHeader().sectionsMovable())

    def test_simple_click_selects_without_loading(self):
        emitted = []
        selected = []
        self.view.preview_track_requested.connect(emitted.append)
        self.view.track_selected.connect(selected.append)
        self.view.set_preview_player_available(True)
        self.view.table.setCurrentIndex(self.view.model.index(0, 0))
        self.application.processEvents()

        self.assertEqual(self.history.selected, [1])
        self.assertEqual(selected, [self.library.rows[0]])
        self.assertEqual(emitted, [])

    def test_double_click_loads_the_selected_track_using_the_same_flow(self):
        emitted = []
        self.view.preview_track_requested.connect(emitted.append)
        self.view.set_preview_player_available(True)
        index = self.view.model.index(0, 0)
        self.view.table.setCurrentIndex(index)
        self.application.processEvents()

        self.view.table.doubleClicked.emit(index)
        self.application.processEvents()

        self.assertEqual(self.history.selected, [1])
        self.assertEqual(emitted, [self.library.rows[0]])

    def test_selection_and_preview_emit_the_existing_track_without_autoplay(self):
        emitted = []
        self.view.preview_track_requested.connect(emitted.append)
        self.view.set_preview_player_available(True)
        self.view.table.setCurrentIndex(self.view.model.index(0, 0))
        self.application.processEvents()

        self.assertEqual(self.history.selected, [1])
        self.view.request_preview_load()
        self.assertEqual(emitted, [self.library.rows[0]])

    def test_selected_track_can_explicitly_request_a_read_only_dj_set(self):
        requested = []
        self.view.dj_set_requested.connect(requested.append)
        self.view.table.setCurrentIndex(self.view.model.index(0, 0))
        self.application.processEvents()
        self.assertTrue(self.view.create_dj_set_button.isEnabled())
        self.view.create_dj_set_button.click()
        self.assertEqual(requested, [self.library.rows[0]])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
