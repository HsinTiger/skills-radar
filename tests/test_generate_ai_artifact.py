import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from generate_ai_artifact import validate_markdown  # noqa: E402


class GenerateAiArtifactTests(unittest.TestCase):
    def test_markdown_requires_length_and_all_headings(self):
        text = "# Report\n\n## Required\n" + ("內容" * 50)
        self.assertEqual(validate_markdown(text, ("## Required",), 20), [])
        errors = validate_markdown("```\nshort", ("## Required",), 20)
        self.assertTrue(any("too short" in error for error in errors))
        self.assertTrue(any("missing heading" in error for error in errors))
        self.assertTrue(any("code fence" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
