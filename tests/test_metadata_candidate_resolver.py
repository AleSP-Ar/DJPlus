import unittest
from app.services.metadata_candidate_resolver import MetadataCandidateResolver, CandidateDTO


class MetadataCandidateResolverTests(unittest.TestCase):
    def setUp(self):
        self.resolver = MetadataCandidateResolver(taxonomy_path="config/genres-v1.json")

    def test_coincident_candidates(self):
        c = [CandidateDTO(source="MB", genre_term="Prog House", style_terms=["organic house"], confidence=0.9),
             CandidateDTO(source="Local", genre_term="progressive_house", style_terms=[], confidence=0.8)]
        r = self.resolver.resolve(c)
        self.assertEqual(r.primary_genre_id, "progressive_house")
        self.assertGreater(r.primary_confidence, 0.0)

    def test_conflict_between_sources(self):
        c = [CandidateDTO(source="MusicBrainz", genre_term="prog house", style_terms=[], confidence=0.9),
             CandidateDTO(source="Discogs", genre_term="progressive_trance", style_terms=[], confidence=0.9)]
        r = self.resolver.resolve(c)
        self.assertEqual(r.conflicts, ["Conflict between sources: multiple distinct resolved genres proposed"])
        self.assertTrue(any("Top genre difference below margin" in w for w in r.warnings))

    def test_ambiguous_term(self):
        c = [CandidateDTO(source="Any", genre_term="progressive", style_terms=[], confidence=0.8)]
        r = self.resolver.resolve(c)
        self.assertEqual(r.primary_genre_id, None)
        self.assertIn("progressive", r.ambiguous)

    def test_unknown_term(self):
        c = [CandidateDTO(source="Any", genre_term="some totally unknown term", style_terms=[], confidence=0.5)]
        r = self.resolver.resolve(c)
        self.assertEqual(r.primary_genre_id, None)
        self.assertIn("some totally unknown term", r.unknown_terms)

    def test_low_confidence(self):
        c = [CandidateDTO(source="Low", genre_term="Prog House", style_terms=[], confidence=0.01)]
        r = self.resolver.resolve(c)
        self.assertLessEqual(r.primary_confidence, 1.0)
        self.assertAlmostEqual(r.primary_confidence, 0.9)

    def test_multiple_styles(self):
        c = [CandidateDTO(source="S", genre_term="psytrance", style_terms=["progressive trance", "organic-house"], confidence=0.9)]
        r = self.resolver.resolve(c)
        # styles should include resolved ids
        self.assertTrue(len(r.styles) >= 1)

    def test_idempotent(self):
        c = [CandidateDTO(source="MB", genre_term="Prog House", style_terms=["organic house"], confidence=0.9)]
        r1 = self.resolver.resolve(c)
        r2 = self.resolver.resolve(c)
        self.assertEqual(r1.primary_genre_id, r2.primary_genre_id)
        self.assertEqual(r1.primary_confidence, r2.primary_confidence)

    def test_primary_confidence_never_exceeds_one(self):
        c = [CandidateDTO(source="MB", genre_term="Prog House", style_terms=[], confidence=1.0),
             CandidateDTO(source="MB2", genre_term="Prog House", style_terms=[], confidence=1.0)]
        r = self.resolver.resolve(c)
        self.assertLessEqual(r.primary_confidence, 1.0)

    def test_duplicate_evidence_keeps_same_confidence(self):
        one = [CandidateDTO(source="MB", genre_term="Prog House", style_terms=[], confidence=0.7)]
        two = [CandidateDTO(source="MB", genre_term="Prog House", style_terms=[], confidence=0.7),
               CandidateDTO(source="MB2", genre_term="Prog House", style_terms=[], confidence=0.7)]
        r_one = self.resolver.resolve(one)
        r_two = self.resolver.resolve(two)
        self.assertEqual(r_one.primary_confidence, r_two.primary_confidence)
        self.assertEqual(r_two.evidence_count, 2)

    def test_zero_confidence_evidence_ignored(self):
        base = [CandidateDTO(source="MB", genre_term="Prog House", style_terms=[], confidence=0.5)]
        extra = [CandidateDTO(source="MB", genre_term="Prog House", style_terms=[], confidence=0.0)]
        r_base = self.resolver.resolve(base)
        r_extra = self.resolver.resolve(base + extra)
        self.assertEqual(r_base.primary_confidence, r_extra.primary_confidence)
        self.assertEqual(r_extra.evidence_count, 1)

    def test_margin_applied_to_normalized_values(self):
        c = [CandidateDTO(source="A", genre_term="Prog House", style_terms=[], confidence=0.55),
             CandidateDTO(source="B", genre_term="Progressive Trance", style_terms=[], confidence=0.45)]
        r = self.resolver.resolve(c)
        self.assertIsNone(r.primary_genre_id)
        self.assertTrue(any("Top genre difference below margin" in w for w in r.warnings))

    def test_exact_normalized_tie_has_no_primary(self):
        c = [CandidateDTO(source="A", genre_term="Prog House", style_terms=[], confidence=0.5),
             CandidateDTO(source="B", genre_term="Progressive Trance", style_terms=[], confidence=0.5)]
        r = self.resolver.resolve(c)
        self.assertIsNone(r.primary_genre_id)
        self.assertTrue(any("Top genre difference below margin" in w for w in r.warnings))


if __name__ == '__main__':
    unittest.main()
