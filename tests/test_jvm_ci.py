"""Real Java acceptance is mandatory, not a silently skipped CI probe."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class JvmCiTests(unittest.TestCase):
    def test_native_matrix_installs_pinned_java21_and_requires_real_probe(self):
        ci = (ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8')
        self.assertIn('actions/setup-java@b843ebf9b913146b38da2eaa7aeddf76074ae1ad # v6.1.0', ci)
        self.assertIn("java-version: '21'", ci)
        self.assertIn('distribution: temurin', ci)
        self.assertIn("REQUIRE_REAL_JAVA: '1'", ci)
        self.assertLess(ci.index('actions/setup-java@'), ci.index('name: Unit tests'))


if __name__ == '__main__':
    unittest.main()
