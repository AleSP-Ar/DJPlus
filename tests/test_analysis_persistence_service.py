import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.action_pipeline import ActionPipeline
from app.services.analysis_change_planner import AnalysisChangePlanner, AnalysisMetadataDTO, AnalysisWritePolicyDTO
from app.services.analysis_persistence_service import AnalysisPersistenceService
from app.services.confirmation_manager import ConfirmationManager, ConfirmationRequestDTO


class _Tracks:
    def __init__(self, track): self.track = track
    def get_by_id(self, track_id): return self.track if track_id == self.track.id else None
    def update_analysis_metadata(self, track, values, provenance=None, commit=True):
        for field, value in values.items(): setattr(track, field, value)
        for field, value in (provenance or {}).items(): setattr(track, field, value)


class _Uow:
    def __init__(self, track): self.tracks = _Tracks(track)
    def __enter__(self): return self
    def __exit__(self, *_): return False


class AnalysisPersistenceServiceTests(unittest.TestCase):
    def setUp(self):
        self.track = SimpleNamespace(id=1, bpm=120, key="C major", energy=30)
        self.pipeline = ActionPipeline(); self.confirmations = ConfirmationManager(self.pipeline)
        self.service = AnalysisPersistenceService(self.pipeline, self.confirmations, lambda: _Uow(self.track))
        self.plan = AnalysisChangePlanner().plan(
            AnalysisMetadataDTO(1, bpm=120, key="C major", energy=30, bpm_confidence=.2, key_confidence=.2, energy_confidence=.2),
            AnalysisMetadataDTO(1, bpm=124, key="D major", energy=60, bpm_confidence=.9, key_confidence=.9, energy_confidence=.9),
            AnalysisWritePolicyDTO("overwrite_lower_confidence"),
        )

    def test_confirmed_apply_is_atomic_and_restore_uses_typed_backup(self):
        proposal = self.service.propose(self.plan)
        result = self.service.apply(self.plan, proposal, ConfirmationRequestDTO(proposal.action_id, datetime.now(timezone.utc)))
        self.assertTrue(result.success)
        self.assertEqual(result.applied_fields, ("bpm", "key", "energy"))
        self.assertEqual((self.track.bpm, self.track.key, self.track.energy), (124, "D major", 60))
        self.assertEqual(self.track.analyzer_version, "pcm-local-v1")
        self.assertEqual(self.track.bpm_confidence, .9)
        restored = self.service.restore(1)
        self.assertTrue(restored.success)
        self.assertEqual((self.track.bpm, self.track.key, self.track.energy), (120, "C major", 30))
        self.assertIsNone(getattr(self.track, "analyzer_version", None))

    def test_requires_confirmation_and_never_writes_skipped_or_unchanged(self):
        plan = AnalysisChangePlanner().plan(AnalysisMetadataDTO(1, bpm=120), AnalysisMetadataDTO(1, bpm=120, key=None))
        proposal = self.service.propose(plan)
        with self.assertRaises(Exception):
            self.service.apply(plan, proposal, ConfirmationRequestDTO("other", datetime.now(timezone.utc)))
        self.assertEqual(self.track.bpm, 120)
        self.assertEqual(self.service.restore(1).success, False)
