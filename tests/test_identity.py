import sys
from pathlib import Path
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_egg


class EggIdentityTests(unittest.TestCase):
    def test_reimports_have_stable_valid_egg_identity(self):
        first = build_egg.export_egg()
        self.assertIn('uuid', first, 'A distributable Egg needs stable identity for repeated imports')
        identity = first['uuid']
        self.assertEqual(str(uuid.UUID(identity)), identity)
        self.assertEqual(build_egg.export_egg()['uuid'], identity)
        self.assertEqual(build_egg.export_egg(update_url='https://example.test/egg.json')['uuid'], identity)


if __name__ == '__main__':
    unittest.main()
