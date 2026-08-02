import unittest
from dataclasses import dataclass

from app.services.assistant_facade import (
    AssistantActionProposalDTO,
    AssistantError,
    AssistantFacade,
    AssistantTool,
    AssistantToolResultDTO,
    DJCompatibilityTool,
    LibraryQueryTool,
    PlaylistInsightTool,
    UnknownAssistantToolError,
)
from app.services.dj_intelligence_service import DJIntelligenceService


@dataclass
class FakePlaylist:
    id: int


@dataclass
class FakeTrack:
    id: int
    bpm: float
    key: str
    energy: float


class FakeLibraryService:
    def count_tracks(self):
        return 42


class FakePlaylistService:
    def list_playlists(self):
        return [FakePlaylist(1), FakePlaylist(2)]

    def count_tracks(self, playlist_id):
        return {1: 3, 2: 5}[playlist_id]


class InvalidTool(AssistantTool):
    name = "invalid"
    description = "invalid"
    input_schema = {}

    def execute(self, input_data):
        return "not a DTO"


class AssistantFacadeTests(unittest.TestCase):
    def setUp(self):
        self.facade = AssistantFacade(
            [
                LibraryQueryTool(FakeLibraryService()),
                PlaylistInsightTool(FakePlaylistService()),
                DJCompatibilityTool(DJIntelligenceService()),
            ]
        )

    def test_facade_uses_only_allowed_tools_and_returns_library_dto(self):
        response = self.facade.execute("library_query")

        self.assertEqual(response.response, "La biblioteca contiene 42 pistas.")
        self.assertEqual(response.data_used, {"track_count": 42})
        self.assertFalse(response.requires_confirmation)
        self.assertFalse(hasattr(self.facade, "repository"))
        self.assertFalse(hasattr(self.facade, "session"))
        self.assertEqual({tool["name"] for tool in self.facade.available_tools()}, {
            "library_query", "playlist_insight", "dj_compatibility"
        })

    def test_invalid_tool_is_rejected_and_tools_must_return_dtos(self):
        with self.assertRaises(UnknownAssistantToolError):
            self.facade.execute("sql")
        with self.assertRaises(AssistantError):
            AssistantFacade([InvalidTool()]).execute("invalid")

    def test_playlist_actions_are_proposals_and_require_confirmation(self):
        response = self.facade.execute("playlist_insight", {"proposal_name": "Progressive Sunset"})

        self.assertTrue(response.requires_confirmation)
        self.assertEqual(response.proposed_actions, (
            AssistantActionProposalDTO(
                "create_playlist",
                "Crear playlist Progressive Sunset",
                {"name": "Progressive Sunset"},
            ),
        ))

    def test_dj_compatibility_tool_returns_explainable_read_only_data(self):
        response = self.facade.execute(
            "dj_compatibility",
            {"track_a": FakeTrack(1, 124, "8A", 70), "track_b": FakeTrack(2, 125, "8A", 75)},
        )

        self.assertEqual(response.data_used["score"], 100)
        self.assertIn("BPM compatible", response.data_used["reasons"][0])
        self.assertEqual(response.proposed_actions, ())
