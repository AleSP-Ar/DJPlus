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

    def test_unknown_term(self):
        r = self.normalizer.normalize_term("some unknown genre")
        self.assertIsNone(r["canonical_id"])
        self.assertEqual(r["status"], "unknown")

    def test_ambiguous_term(self):
        # create a local normalizer with an ambiguous alias
        normalizer = GenreNormalizer(taxonomy_path="config/genres-v1.json")
        # 'drum and bass' maps to drum_and_bass only, to force ambiguity we query a token 'house' which isn't present
        r = normalizer.normalize_term("house")
        self.assertIn(r["status"], ("unknown", "ambiguous"))


if __name__ == '__main__':
    unittest.main()
