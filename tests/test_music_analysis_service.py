import unittest
from dataclasses import dataclass
from datetime import datetime, timezone

from app.services.music_analysis_service import (
    AnalysisContractError,
    AnalysisError,
    AnalysisFeature,
    AnalysisProviderError,
    AnalysisResultDTO,
    MockAnalyzerProvider,
    MusicAnalysisService,
    UnsupportedAnalysisFeatureError,
)


@dataclass
class FakeTrack:
    id: int


class MusicAnalysisServiceTests(unittest.TestCase):
    def setUp(self):
        self.track = FakeTrack(id=12)
        self.provider = MockAnalyzerProvider(
            values={
                AnalysisFeature.BPM: 124.0,
                AnalysisFeature.KEY: "8A",
                AnalysisFeature.ENERGY: 0.72,
                AnalysisFeature.DURATION: 210.0,
                AnalysisFeature.WAVEFORM: "future://waveform/12",
            },
            confidence=0.86,
        )
        self.service = MusicAnalysisService(self.provider)

    def test_service_uses_the_configured_provider_for_requested_features(self):
        results = self.service.analyze(self.track, ["bpm", AnalysisFeature.KEY])

        self.assertEqual([result.feature_type for result in results], [AnalysisFeature.BPM, AnalysisFeature.KEY])
        self.assertEqual(results[0].value, 124.0)
        self.assertEqual(self.provider.calls[-1], (self.track, (AnalysisFeature.BPM, AnalysisFeature.KEY)))

    def test_mock_provider_returns_versioned_dto_results_for_all_supported_features(self):
        results = self.service.analyze(self.track, list(self.provider.supported_features()))

        self.assertEqual({result.feature_type for result in results}, set(AnalysisFeature))
        self.assertTrue(all(result.track_id == 12 for result in results))
        self.assertTrue(all(result.provider == "mock" and result.provider_version == "1.0" for result in results))
        self.assertTrue(all(result.created_at.tzinfo is not None for result in results))

    def test_result_dto_validates_required_contract_fields(self):
        result = AnalysisResultDTO(
            track_id=2,
            feature_type=AnalysisFeature.ENERGY,
            value=0.5,
            provider="test",
            provider_version="0.1",
            confidence=0.5,
            created_at=datetime.now(timezone.utc),
        )

        self.assertEqual(result.feature_type, AnalysisFeature.ENERGY)
        with self.assertRaises(AnalysisContractError):
            AnalysisResultDTO(2, AnalysisFeature.BPM, 120, "test", "0.1", 1.5)
        with self.assertRaises(AnalysisContractError):
            AnalysisResultDTO(2, AnalysisFeature.BPM, 120, "test", "0.1", 0.5, datetime.now())

    def test_rejects_unsupported_features_invalid_tracks_and_missing_mock_values(self):
        with self.assertRaises(UnsupportedAnalysisFeatureError):
            self.service.analyze(self.track, ["unknown"])
        with self.assertRaises(AnalysisError):
            self.service.analyze(FakeTrack(id=0), ["bpm"])
        with self.assertRaises(AnalysisProviderError):
            MockAnalyzerProvider(values={}).analyze(self.track, ["bpm"])
