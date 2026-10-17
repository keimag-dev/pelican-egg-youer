"""Keep the user-selected upstream icon inside the standalone Egg."""
import base64
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_egg


class IconTests(unittest.TestCase):
    def test_embeds_exact_user_selected_youer_icon(self):
        data = (ROOT / 'assets/youer.webp').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), '403e9f87f5526367a9319f7162f9e7be419f7856a72328e17ea8765f5bbc6958')
        expected = 'data:image/webp;base64,' + base64.b64encode(data).decode('ascii')
        self.assertEqual(build_egg.export_egg().get('icon'), expected)


if __name__ == '__main__':
    unittest.main()
