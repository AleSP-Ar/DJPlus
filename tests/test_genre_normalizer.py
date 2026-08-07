import unittest
from app.services.genre_normalizer import GenreNormalizer


class GenreNormalizerTests(unittest.TestCase):
    def setUp(self):
        self.normalizer = GenreNormalizer(taxonomy_path="config/genres-v1.json")

    def test_exact_canonical_id(self):
        r = self.normalizer.normalize_term("progressive_house")
        self.assertEqual(r["canonical_id"], "progressive_house")
        self.assertEqual(r["status"], "exact")
        self.assertEqual(r["confidence"], 1.0)

    def test_alias_prog_house(self):
        r = self.normalizer.normalize_term("prog house")
        self.assertEqual(r["canonical_id"], "progressive_house")
        self.assertEqual(r["status"], "alias")
        self.assertAlmostEqual(r["confidence"], 0.9)

    def test_alias_case_and_punctuation(self):
        r = self.normalizer.normalize_term("Progressive-House")
        self.assertEqual(r["canonical_id"], "progressive_house")

    def test_new_genres_are_supported(self):
        for term, expected in [
            ("deep_house", "deep_house"),
            ("afro_house", "afro_house"),
            ("tech_house", "tech_house"),
            ("melodic_house", "melodic_house"),
            ("melodic_techno", "melodic_techno"),
            ("peak_time_techno", "peak_time_techno"),
            ("tech_trance", "tech_trance"),
            ("uplifting_trance", "uplifting_trance"),
        ]:
            result = self.normalizer.normalize_term(term)
            self.assertEqual(result["canonical_id"], expected)
            self.assertEqual(result["status"], "exact")
            self.assertEqual(result["confidence"], 1.0)

    def test_uplifting_trance_alias(self):
        result = self.normalizer.normalize_term("uplifting-trance")
        self.assertEqual(result["canonical_id"], "uplifting_trance")
        self.assertEqual(result["status"], "exact")

    def test_unknown_term(self):
        r = self.normalizer.normalize_term("some unknown genre")
        self.assertIsNone(r["canonical_id"])
        self.assertEqual(r["status"], "unknown")

    def test_ambiguous_term(self):
        normalizer = GenreNormalizer(taxonomy_path="config/genres-v1.json")
        r = normalizer.normalize_term("house")
        self.assertIn(r["status"], ("unknown", "ambiguous"))


if __name__ == '__main__':
    unittest.main()
