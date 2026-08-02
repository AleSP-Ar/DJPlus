import unittest

from app.services.assistant_context import (
    AssistantContextError,
    AssistantContextDTO,
    AssistantContextBuilder,
    ContextProvider,
    DJContextProvider,
    LibraryContextProvider,
)


class FakeLibraryService:
    def count_tracks(self):
        return 42


class FakeScoringEngine:
    WEIGHTS = {"bpm": 50, "key": 30, "energy": 20}


class FakeDJService:
    scoring_engine = FakeScoringEngine()


class FilteredContextProvider(ContextProvider):
    def get_context(self):
        return AssistantContextDTO(
            available_data={
                "safe": "value",
                "filepath": "C:/private/music.mp3",
                "file_path": "C:/private/alternate.mp3",
                "sql": "SELECT * FROM tracks",
                "nested": {"count": 2, "session": "blocked"},
                "object": object(),
            },
            data_sources=("filtered",),
        )


class AssistantContextTests(unittest.TestCase):
    def setUp(self):
        self.builder = AssistantContextBuilder(
            [LibraryContextProvider(FakeLibraryService()), DJContextProvider(FakeDJService())],
            context_version="1.0",
        )

    def test_builds_valid_versioned_context_from_allowed_providers(self):
        context = self.builder.build()

        self.assertEqual(context.context_version, "1.0")
        self.assertEqual(context.data_sources, ("library", "dj_intelligence"))
        self.assertEqual(context.available_data["library"], {"track_count": 42})
        self.assertTrue(context.available_data["dj_intelligence"]["compatibility_available"])
        self.assertIsNotNone(context.timestamp.tzinfo)

    def test_filters_sensitive_and_non_dto_data(self):
        context = AssistantContextBuilder([FilteredContextProvider()]).build()

        self.assertEqual(context.available_data["filtered"], {"safe": "value", "nested": {"count": 2}})
        self.assertNotIn("filepath", context.available_data["filtered"])
        self.assertNotIn("file_path", context.available_data["filtered"])
        self.assertNotIn("sql", context.available_data["filtered"])
        self.assertNotIn("object", context.available_data["filtered"])

    def test_rejects_non_allowed_providers_and_duplicate_sources(self):
        with self.assertRaises(TypeError):
            AssistantContextBuilder([object()])
        with self.assertRaises(AssistantContextError):
            AssistantContextBuilder([LibraryContextProvider(FakeLibraryService()), LibraryContextProvider(FakeLibraryService())]).build()
