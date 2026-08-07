import unittest
import tempfile
import json
from pathlib import Path

from app.services.style_normalizer import StyleNormalizer


class StyleNormalizerTests(unittest.TestCase):
    def setUp(self):
        self.normalizer = StyleNormalizer(taxonomy_path="config/styles-v1.json")

    def test_exact_style(self):
        r = self.normalizer.normalize_term("Deep")
        self.assertEqual(r["resolved_id"], "deep")
        self.assertEqual(r["status"], "exact")
        self.assertAlmostEqual(r["confidence"], 1.0)

    def test_alias_known(self):
        r = self.normalizer.normalize_term("organic-house")
        self.assertEqual(r["resolved_id"], "organic")
        self.assertEqual(r["status"], "alias")
        self.assertAlmostEqual(r["confidence"], 0.9)

    def test_unknown_style(self):
        r = self.normalizer.normalize_term("totally_unknown_style")
        self.assertIsNone(r["resolved_id"])
        self.assertEqual(r["status"], "unknown")

    def test_empty_term(self):
        r = self.normalizer.normalize_term("")
        self.assertIsNone(r["resolved_id"])
        self.assertEqual(r["status"], "unknown")
        r2 = self.normalizer.normalize_term(None)
        self.assertIsNone(r2["resolved_id"])

    def test_invalid_config(self):
        # styles must be an object/dict
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump({"version": "1", "styles": []}, tmp)
            tmp_path = tmp.name
        with self.assertRaises(ValueError):
            StyleNormalizer(taxonomy_path=tmp_path)

    def test_alias_conflict(self):
        # create a taxonomy with conflicting aliases
        data = {"version": "1", "styles": {
            "a": {"label": "A", "aliases": ["shared"]},
            "b": {"label": "B", "aliases": ["shared"]}
        }}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(data, tmp)
            tmp_path = tmp.name
        sn = StyleNormalizer(taxonomy_path=tmp_path)
        r = sn.normalize_term("shared")
        self.assertEqual(r["status"], "ambiguous")
        self.assertGreaterEqual(len(r.get("candidates", [])), 2)

    def test_result_deterministic(self):
        r1 = self.normalizer.normalize_term("Deep")
        r2 = self.normalizer.normalize_term("Deep")
        self.assertEqual(r1, r2)

    def test_genre_not_resolved_as_style(self):
        # genres from genres-v1.json must not resolve as styles
        r = self.normalizer.normalize_term("progressive_house")
        self.assertEqual(r["status"], "unknown")


if __name__ == '__main__':
    unittest.main()
