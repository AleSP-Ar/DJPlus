import inspect
import unittest
from dataclasses import dataclass

from app.services.assistant_facade import AssistantError
from app.services.library_tools import CollectionTool, LibraryQueryTool, NaturalLibraryQueryInterpreter, PlaylistTool
from app.services.tool_dispatcher import ToolCallDTO, ToolDispatcher, ToolRegistry


@dataclass(frozen=True)
class FakePlaylist:
    id: int


@dataclass(frozen=True)
class FakeCollection:
    id: int


class FakeLibraryService:
    def count_tracks(self):
        return 42


class SearchableFakeLibraryService(FakeLibraryService):
    def __init__(self):
        self.calls = []

    def query(self, text="", **filters):
        self.calls.append((text, filters))
        return (FakeTrack(1, "First", "Artist"),), True

    def load_more(self):
        self.calls.append(("load_more", {}))
        return (FakeTrack(2, "Second", "Artist"),), False

    def count_results(self):
        return 3


@dataclass(frozen=True)
class FakeTrack:
    id: int
    title: str
    artist: str
    album: str = "Album"


class FakePlaylistService:
    def __init__(self):
        self.write_calls = []

    def list_playlists(self):
        return (FakePlaylist(1), FakePlaylist(2))

    def count_tracks(self, playlist_id):
        return {1: 3, 2: 5}[playlist_id]

    def create_playlist(self, name):
        self.write_calls.append(name)


class FakeCollectionService:
    def __init__(self):
        self.write_calls = []

    def list_collections(self):
        return (FakeCollection(10), FakeCollection(11))

    def count_tracks(self, collection_id):
        return {10: 4, 11: 6}[collection_id]

    def create_collection(self, name):
        self.write_calls.append(name)


class LibraryToolsTests(unittest.TestCase):
    def setUp(self):
        self.playlists = FakePlaylistService()
        self.collections = FakeCollectionService()
        self.registry = ToolRegistry.default(FakeLibraryService(), self.playlists, self.collections)
        self.dispatcher = ToolDispatcher(self.registry)

    def test_default_registry_registers_the_library_tools(self):
        self.assertEqual(self.registry.registered_tool_names(), ("library_query", "playlist", "collection"))

    def test_library_query_returns_immutable_typed_read_only_data(self):
        result = self.dispatcher.dispatch(ToolCallDTO("library_query"))

        self.assertTrue(result.success)
        self.assertEqual(result.result.data_used["track_count"], 42)
        with self.assertRaises(TypeError):
            result.result.data_used["track_count"] = 0

    def test_playlist_and_collection_tools_return_proposals_without_writes(self):
        playlist = self.dispatcher.dispatch(ToolCallDTO("playlist", {"action": "propose_create", "name": "Sunset"}))
        collection = self.dispatcher.dispatch(ToolCallDTO(
            "collection", {"action": "propose_create", "name": "Peak", "collection_type": "smart"}
        ))

        self.assertEqual(playlist.result.data_used, {"playlist_count": 2, "playlist_track_count": 8})
        self.assertEqual(playlist.result.proposed_actions[0].payload, {"name": "Sunset"})
        self.assertEqual(collection.result.proposed_actions[0].payload, {"name": "Peak", "collection_type": "smart"})
        with self.assertRaises(TypeError):
            collection.result.proposed_actions[0].payload["name"] = "Changed"
        self.assertEqual(self.playlists.write_calls, [])
        self.assertEqual(self.collections.write_calls, [])

    def test_tools_reject_invalid_input_dtos_and_have_no_persistence_imports(self):
        with self.assertRaises(AssistantError):
            PlaylistTool(self.playlists).execute({"action": "propose_create", "name": " "})
        with self.assertRaises(AssistantError):
            CollectionTool(self.collections).execute({"collection_type": "unknown"})
        with self.assertRaises(AssistantError):
            LibraryQueryTool(FakeLibraryService()).execute({"unexpected": True})

        source = inspect.getsource(__import__("app.services.library_tools", fromlist=["*"]))
        for forbidden in ("app.repository", "sqlalchemy", "sqlite3", "Repository"):
            self.assertNotIn(forbidden, source)

    def test_natural_language_query_composes_existing_read_only_filters_through_library_service(self):
        library = SearchableFakeLibraryService()
        tool = LibraryQueryTool(library)

        result = tool.execute({"query": '"Sunset" género house BPM entre 120 y 128 key 8A mínimo 4 estrellas favoritos'})

        self.assertEqual(library.calls, [("Sunset", {
            "genre": "house", "bpm_min": 120.0, "bpm_max": 128.0, "key": "8A", "rating_min": 4, "favorite": True,
        })])
        self.assertEqual(result.data_used["track_count"], 3)
        self.assertTrue(result.data_used["interpreted"])
        self.assertEqual(result.proposed_actions, ())

    def test_natural_query_supports_text_favorite_and_bound_filters(self):
        interpreter = NaturalLibraryQueryInterpreter()

        parsed, explanation = interpreter.interpret('buscar techno menos de 130 BPM no favoritos rating 5')

        self.assertIsNone(explanation)
        self.assertEqual(parsed.text, "techno")
        self.assertEqual(parsed.bpm_max, 130.0)
        self.assertFalse(parsed.favorite)
        self.assertEqual((parsed.rating_min, parsed.rating_max), (5, 5))

    def test_uninterpretable_filter_returns_explanatory_read_only_response_without_service_query(self):
        library = SearchableFakeLibraryService()

        result = LibraryQueryTool(library).execute({"query": "bpm muy rapido"})

        self.assertFalse(result.data_used["interpreted"])
        self.assertIn("BPM", result.response)
        self.assertEqual(library.calls, [])

    def test_natural_search_returns_typed_first_page_summary_and_load_more(self):
        library = SearchableFakeLibraryService()
        tool = LibraryQueryTool(library)

        first = tool.execute({"query": "genero house"})
        more = tool.execute({"load_more": True})

        first_page = first.data_used["search_result"]
        more_page = more.data_used["search_result"]
        self.assertEqual((first_page.total_matches, first_page.page_number, first_page.page_items[0].title), (3, 1, "First"))
        self.assertTrue(first_page.has_more)
        self.assertEqual((more_page.page_number, more_page.page_items[0].title, more_page.has_more), (2, "Second", False))
        self.assertIn("Cargue mas resultados", more.response)

    def test_load_more_without_search_and_zero_results_are_clear(self):
        library = SearchableFakeLibraryService()
        tool = LibraryQueryTool(library)

        missing = tool.execute({"load_more": True})

        self.assertFalse(missing.data_used["interpreted"])
        self.assertIn("busqueda previa", missing.response)

        class ZeroResultLibrary(SearchableFakeLibraryService):
            def count_results(self):
                return 0

        zero = LibraryQueryTool(ZeroResultLibrary()).execute({"query": "genero house"})
        self.assertIn("No encontre resultados", zero.response)
