import unittest
from pathlib import Path

from app.version import VERSION


class ReleaseVersionTests(unittest.TestCase):
    """Keep the canonical runtime version aligned with current release records."""

    def test_current_release_references_match_the_canonical_version(self):
        root = Path(__file__).resolve().parents[1]
        current_release_files = (
            root / "README.md",
            root / "docs" / "roadmap" / "MILESTONES.md",
            root / "docs" / "releases" / "V1_0_0_RC1_RELEASE.md",
        )
        expected = f"v{VERSION}"
        for path in current_release_files:
            self.assertIn(expected, path.read_text(encoding="utf-8"), path.name)

