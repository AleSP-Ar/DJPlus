import inspect
import unittest

from app.services.analysis_change_planner import AnalysisChangePlanner, AnalysisChangePlanningError, AnalysisMetadataDTO, AnalysisWritePolicyDTO


class AnalysisChangePlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = AnalysisChangePlanner()
        self.existing = AnalysisMetadataDTO(7, bpm=120, key="C major", energy=40, bpm_confidence=0.4, key_confidence=0.8, energy_confidence=0.3)
        self.analyzed = AnalysisMetadataDTO(7, bpm=124, key="c major", energy=65, bpm_confidence=0.9, key_confidence=0.9, energy_confidence=0.7)

    def test_never_overwrite_returns_deterministic_preview_and_conflicts(self):
        plan = self.planner.plan(self.existing, self.analyzed)

        self.assertEqual(tuple(change.classification for change in plan.changes), ("conflict", "unchanged", "conflict"))
        self.assertEqual(tuple(change.field for change in plan.changes), ("bpm", "key", "energy"))
        self.assertIn("bpm: conflict", plan.preview)
        self.assertFalse(plan.has_applicable_changes)

    def test_confidence_policy_force_new_and_skipped_are_explicit(self):
        lower_confidence = self.planner.plan(self.existing, self.analyzed, AnalysisWritePolicyDTO("overwrite_lower_confidence"))
        self.assertEqual(tuple(change.classification for change in lower_confidence.changes), ("new", "unchanged", "new"))
        self.assertTrue(lower_confidence.has_applicable_changes)

        force = self.planner.plan(self.existing, AnalysisMetadataDTO(7, bpm=119, key=None, energy=41, bpm_confidence=.1, energy_confidence=.1), AnalysisWritePolicyDTO("force"))
        self.assertEqual(tuple(change.classification for change in force.changes), ("new", "skipped", "new"))

        brand_new = self.planner.plan(AnalysisMetadataDTO(7), AnalysisMetadataDTO(7, bpm=128, bpm_confidence=.8))
        self.assertEqual(tuple(change.classification for change in brand_new.changes), ("new", "skipped", "skipped"))

    def test_validates_contract_and_has_no_persistence_dependencies(self):
        with self.assertRaises(AnalysisChangePlanningError):
            AnalysisMetadataDTO(1, bpm=None, bpm_confidence=.5)
        with self.assertRaises(AnalysisChangePlanningError):
            self.planner.plan(AnalysisMetadataDTO(1), AnalysisMetadataDTO(2))
        with self.assertRaises(AnalysisChangePlanningError):
            AnalysisWritePolicyDTO("automatic")
        source = inspect.getsource(__import__("app.services.analysis_change_planner", fromlist=["*"]))
        for forbidden in ("app.repository", "sqlite3", "sqlalchemy", "Repository"):
            self.assertNotIn(forbidden, source)
