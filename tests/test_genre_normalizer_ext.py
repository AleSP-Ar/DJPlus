import unittest
import tempfile
import json
from pathlib import Path
from app.services.genre_normalizer import GenreNormalizer


class GenreNormalizerExtTests(unittest.TestCase):
    def test_known_alias_from_seed(self):
        n = GenreNormalizer("config/genres-v1.json")
        r = n.normalize_term("Prog House")
        self.assertEqual(r["resolved_id"], "progressive_house")
        self.assertEqual(r["resolution_status"], "alias")
        self.assertAlmostEqual(r["confidence"], 0.9)

    def test_new_taxonomy_entries_are_resolved(self):
        n = GenreNormalizer("config/genres-v1.json")
        for term, expected in [
            ("Deep House", "deep_house"),
            ("Afro House", "afro_house"),
            ("Tech House", "tech_house"),
            ("Melodic House", "melodic_house"),
            ("Melodic Techno", "melodic_techno"),
            ("Peak Time Techno", "peak_time_techno"),
            ("Tech Trance", "tech_trance"),
            ("Uplifting Trance", "uplifting_trance"),
        ]:
            result = n.normalize_term(term)
            self.assertEqual(result["resolved_id"], expected)
            self.assertEqual(result["resolution_status"], "exact")

    def test_explicit_ambiguous_term_progressive(self):
        n = GenreNormalizer("config/genres-v1.json")
        r = n.normalize_term("progressive")
        self.assertEqual(r["resolution_status"], "ambiguous")
        self.assertIsNone(r["resolved_id"])
        self.assertIn("progressive_house", r["candidates"])
        self.assertIn("progressive_trance", r["candidates"])
        self.assertAlmostEqual(r["confidence"], 0.0)
        self.assertTrue(len(r["warnings"]) > 0)

    def test_unknown_term(self):
        n = GenreNormalizer("config/genres-v1.json")
        r = n.normalize_term("this is totally unknown")
        self.assertEqual(r["resolution_status"], "unknown")
        self.assertIsNone(r["resolved_id"])

    def test_alias_conflict_rejected_unless_declared(self):
        js = {
            "version": "1",
            "genres": {
                "g1": {"label": "G1", "aliases": ["shared"]},
                "g2": {"label": "G2", "aliases": ["shared"]}
            }
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tf:
            json.dump(js, tf)
            tf.flush()
            path = tf.name
        with self.assertRaises(ValueError):
            GenreNormalizer(path)

    def test_duplicate_key_detection(self):
        # craft JSON text with duplicated key in genres
        txt = '{"version": "1", "genres": {"a": {"label":"A","aliases":[]}, "a": {"label":"A2","aliases":[]}}}'
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tf:
            tf.write(txt)
            tf.flush()
            path = tf.name
        with self.assertRaises(ValueError):
            GenreNormalizer(path)

    def test_malformed_json_raises(self):
        txt = '{"version": "1", "genres": {'
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tf:
            tf.write(txt)
            tf.flush()
            path = tf.name
        with self.assertRaises(ValueError):
            GenreNormalizer(path)

    def test_aliases_invalid_type(self):
        js = {"version": "1", "genres": {"g1": {"label": "G1", "aliases": "not-a-list"}}}
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tf:
            json.dump(js, tf)
            tf.flush()
            path = tf.name
        with self.assertRaises(ValueError):
            GenreNormalizer(path)

    def test_version_missing(self):
        js = {"genres": {"g1": {"label": "G1", "aliases": []}}}
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tf:
            json.dump(js, tf)
            tf.flush()
            path = tf.name
        with self.assertRaises(ValueError):
            GenreNormalizer(path)

    def test_idempotent_same_result(self):
        n = GenreNormalizer("config/genres-v1.json")
        a = n.normalize_term("Prog House")
        b = n.normalize_term("Prog House")
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
