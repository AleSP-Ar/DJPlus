import unittest

from app.services.discogs_metadata_classifier import (
    DiscogsMetadataClassifier,
    DiscogsReleaseEvidenceDTO,
    DiscogsClassificationResultDTO,
)
from app.services.metadata_candidate_resolver import CandidateDTO


class DiscogsMetadataClassifierTests(unittest.TestCase):
    def setUp(self):
        self.classifier = DiscogsMetadataClassifier(
            taxonomy_path="config/genres-v1.json",
            style_taxonomy_path="config/styles-v1.json",
        )

    def test_classify_genre_and_style_terms(self):
        evidence = DiscogsReleaseEvidenceDTO(
            raw_genres=("progressive trance", "Electronic"),
            raw_styles=("organic-house",),
            confidence=0.85,
        )
        result = self.classifier.classify(evidence)

        self.assertIsInstance(result, DiscogsClassificationResultDTO)
        self.assertEqual(result.broad_terms, ("electronic",))
        self.assertEqual(result.ambiguous_terms, ())
        self.assertEqual(result.unknown_terms, ())
        self.assertEqual(len(result.candidates), 2)
        self.assertIsInstance(result.candidates[0], CandidateDTO)
        self.assertEqual(result.candidates[0].genre_term, "progressive trance")
        self.assertEqual(result.candidates[0].style_terms, [])
        self.assertEqual(result.candidates[1].genre_term, None)
        self.assertEqual(result.candidates[1].style_terms, ["organic-house"])
        self.assertEqual(result.candidates[0].confidence, 0.85)

    def test_broad_terms_are_reported_but_do_not_create_candidates(self):
        evidence = DiscogsReleaseEvidenceDTO(
            raw_genres=("Electronic", "House", "Techno", "Trance", "Music"),
            raw_styles=(),
            confidence=0.7,
        )
        result = self.classifier.classify(evidence)

        self.assertEqual(result.candidates, ())
        self.assertEqual(result.broad_terms, ("electronic", "house", "techno", "trance"))
        self.assertEqual(result.unknown_terms, ("music",))

    def test_classify_raises_on_invalid_evidence(self):
        with self.assertRaises(TypeError):
            self.classifier.classify(None)

    def test_classify_resolves_genre_from_style_input(self):
        evidence = DiscogsReleaseEvidenceDTO(
            raw_genres=(),
            raw_styles=("Progressive House",),
            confidence=0.75,
        )
        result = self.classifier.classify(evidence)

        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].genre_term, "Progressive House")
        self.assertEqual(result.candidates[0].style_terms, [])

    def test_classify_resolves_style_from_genre_input(self):
        evidence = DiscogsReleaseEvidenceDTO(
            raw_genres=("Deep House",),
            raw_styles=("Hypnotic",),
            confidence=0.8,
        )
        result = self.classifier.classify(evidence)

        self.assertEqual(len(result.candidates), 2)
        self.assertEqual(result.candidates[0].genre_term, "Deep House")
        self.assertEqual(result.candidates[0].style_terms, [])
        self.assertEqual(result.candidates[1].genre_term, None)
        self.assertEqual(result.candidates[1].style_terms, ["Hypnotic"])

    def test_classify_preserves_ambiguous_and_unknown_terms(self):
        evidence = DiscogsReleaseEvidenceDTO(
            raw_genres=("Progressive", "Unknown Genre"),
            raw_styles=("Mystery Style",),
            confidence=0.9,
        )
        result = self.classifier.classify(evidence)

        self.assertIn("progressive", result.ambiguous_terms)
        self.assertIn("unknown genre", result.unknown_terms)
        self.assertIn("mystery style", result.unknown_terms)

    def test_classify_deduplicates_multiple_genres_and_styles(self):
        evidence = DiscogsReleaseEvidenceDTO(
            raw_genres=("Deep House", "Progressive Trance"),
            raw_styles=("Deep", "Hypnotic", "Hypnotic", "Driving"),
            confidence=0.6,
        )
        result = self.classifier.classify(evidence)

        self.assertEqual([candidate.genre_term for candidate in result.candidates if candidate.genre_term], ["Deep House", "Progressive Trance"])
        self.assertEqual(result.candidates[-1].style_terms, ["Deep", "Driving", "Hypnotic"])
        self.assertEqual(result.candidates[-1].genre_term, None)

    def test_empty_input_returns_empty_result(self):
        result = self.classifier.classify(DiscogsReleaseEvidenceDTO(raw_genres=(), raw_styles=(), confidence=0.5))
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.broad_terms, ())
        self.assertEqual(result.ambiguous_terms, ())
        self.assertEqual(result.unknown_terms, ())


if __name__ == '__main__':
    unittest.main()
