import unittest
from dataclasses import dataclass

from app.services.dj_intelligence_service import (
    CompatibilityError,
    CompatibilityResultDTO,
    DJIntelligenceService,
)


@dataclass
class FakeTrack:
    id: int
    bpm: float | None = None
    key: str | None = None
    energy: float | None = None


class DJIntelligenceServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = DJIntelligenceService()

    def test_scores_compatible_tracks_with_explainable_reasons(self):
        result = self.service.evaluate_compatibility(
            FakeTrack(1, bpm=124, key="8A", energy=70),
            FakeTrack(2, bpm=125, key="8a", energy=76),
        )

        self.assertEqual(result.score, 100)
        self.assertEqual(result.confidence, 1.0)
        self.assertIn("BPM compatible (Δ 1)", result.reasons)
        self.assertIn("Key compatible", result.reasons)
        self.assertIn("Energía similar (Δ 6)", result.reasons)

    def test_scores_incompatible_tracks_deterministically(self):
        first = FakeTrack(3, bpm=120, key="8A", energy=10)
        second = FakeTrack(4, bpm=140, key="2B", energy=90)

        first_result = self.service.evaluate_compatibility(first, second)
        second_result = self.service.evaluate_compatibility(first, second)

        self.assertEqual(first_result, second_result)
        self.assertEqual(first_result.score, 0)
        self.assertEqual(first_result.confidence, 1.0)
        self.assertIn("BPM distante (Δ 20)", first_result.reasons)
        self.assertIn("Key diferente", first_result.reasons)
        self.assertIn("Energía distante (Δ 80)", first_result.reasons)

    def test_missing_data_reduces_confidence_and_is_explained(self):
        result = self.service.evaluate_compatibility(FakeTrack(5), FakeTrack(6))

        self.assertEqual(result.score, 0)
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.reasons, ("BPM no disponible", "Key no disponible", "Energía no disponible"))

    def test_validates_result_and_track_identity(self):
        with self.assertRaises(CompatibilityError):
            self.service.evaluate_compatibility(FakeTrack(0), FakeTrack(2))
        with self.assertRaises(CompatibilityError):
            CompatibilityResultDTO(1, 2, 101, ("motivo",), 1.0)
