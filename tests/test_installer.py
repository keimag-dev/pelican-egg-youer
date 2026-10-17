import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import installer


class ResolutionTests(unittest.TestCase):
    def test_latest_means_highest_numeric_build_not_list_position(self):
        rows = [{"id": 7, "file_sha256": "a" * 64},
                {"id": 920, "file_sha256": "b" * 64},
                {"id": 91, "file_sha256": "c" * 64}]
        self.assertEqual(installer.resolve_build(rows, "latest"), rows[1])

    def test_exact_build_and_invalid_metadata_fail_closed(self):
        rows = [{"id": 7, "file_sha256": "a" * 64},
                {"id": 920, "file_sha256": "b" * 64}]
        self.assertEqual(installer.resolve_build(rows, "7"), rows[0])
        for bad in ("999", "7x", "07", "", "1;echo bad"):
            with self.subTest(build=bad), self.assertRaises(ValueError):
                installer.resolve_build(rows, bad)
        for bad_rows in ([], {}, [{"id": "7", "file_sha256": "a" * 64}],
                         [{"id": 7, "file_sha256": "bad"}], rows + [rows[0]]):
            with self.subTest(rows=bad_rows), self.assertRaises(ValueError):
                installer.resolve_build(bad_rows, "latest")


class ConfigTests(unittest.TestCase):
    def test_defaults_and_safe_properties_reject_injection(self):
        cfg = installer.parse_config({})
        self.assertEqual(cfg["MINECRAFT_VERSION"], "1.21.1")
        self.assertEqual(cfg["SERVER_JARFILE"], "server.jar")
        for key, bad in (("MINECRAFT_VERSION", "latest"), ("MINECRAFT_VERSION", "../1"),
                         ("SERVER_JARFILE", "../x.jar"), ("SERVER_JARFILE", "-x.jar"),
                         ("SERVER_JARFILE", "x.jar;id"), ("MAX_PLAYERS", "0"),
                         ("GAMEMODE", "potato"), ("DIFFICULTY", "hard\nx=1"),
                         ("ONLINE_MODE", "yes"), ("VIEW_DISTANCE", "33"),
                         ("LEVEL_NAME", "../world"), ("SERVER_NAME", "x\ny=1"),
                         ("MOTD", "x\ny=1"), ("HEAP_MB", "010"), ("HEAP_MB", "511"),
                         ("NATIVE_HEADROOM_MB", "0")):
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                installer.parse_config({key: bad})
        cfg = installer.parse_config({"MOTD": "日本語 = test\\nnext", "WHITELIST": "true"})
        text = installer.properties_text(cfg)
        self.assertIn("white-list=true\n", text)
        self.assertIn(r"motd=\u65e5\u672c\u8a9e = test\\nnext", text)
        self.assertNotIn("eula=true", text)

    def test_properties_preserve_leading_spaces_as_literal_content(self):
        text = installer.properties_text(installer.parse_config({"MOTD": "  padded"}))
        self.assertIn("motd=\\ \\ padded\n", text)


class DownloadTests(unittest.TestCase):
    def test_verified_atomic_jar_replacement_and_cleanup_on_failure(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as z:
            z.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\nMain-Class: example.Main\n")
        good = payload.getvalue()
        digest = hashlib.sha256(good).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "server.jar"
            target.write_bytes(b"previous jar")
            for data, sha in ((good, "0" * 64), (b"not a jar", hashlib.sha256(b"not a jar").hexdigest())):
                with self.subTest(data=data[:8]), self.assertRaises(ValueError):
                    installer.download_jar(target, "https://example.test/file", sha,
                                           lambda url: io.BytesIO(data))
                self.assertEqual(target.read_bytes(), b"previous jar")
                self.assertEqual([p.name for p in Path(tmp).iterdir()], ["server.jar"])
            installer.download_jar(target, "https://example.test/file", digest,
                                   lambda url: io.BytesIO(good))
            self.assertEqual(target.read_bytes(), good)
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["server.jar"])


    def test_interrupted_transport_leaves_previous_jar_and_no_temporary_file(self):
        class Interrupted(io.BytesIO):
            def read(self, size=-1):
                raise ConnectionResetError("connection lost")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp, "server.jar")
            target.write_bytes(b"original")
            with self.assertRaises(ConnectionResetError):
                installer.download_jar(target, "https://example.test/jar", "a" * 64,
                                       lambda url: Interrupted(b"partial"))
            self.assertEqual(target.read_bytes(), b"original")
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["server.jar"])


class InstallTests(unittest.TestCase):
    def test_fresh_install_then_upgrade_preserves_all_user_state(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as z:
            z.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
        jar = payload.getvalue()
        sha = hashlib.sha256(jar).hexdigest()
        calls = []
        def transport(url):
            calls.append(url)
            if url.endswith("/builds"):
                import json
                return io.BytesIO(json.dumps([{"id": 920, "file_sha256": sha}]).encode())
            return io.BytesIO(jar)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installer.install(root, {}, "#!/bin/bash\nexec java\n", transport)
            self.assertEqual((root / "server.jar").read_bytes(), jar)
            self.assertEqual((root / "eula.txt").read_text(), "eula=false\n")
            state = {"server.properties": b"# custom\r\nmotd=Mine\r\n", "eula.txt": b"eula=true\n",
                     "world/level.dat": b"world", "mods/private.jar": b"mod",
                     "plugins/plugin.jar": b"plugin", "custom.txt": b"owned"}
            for name, data in state.items():
                p = root / name
                p.parent.mkdir(exist_ok=True, parents=True)
                p.write_bytes(data)
            installer.install(root, {"YOUER_BUILD": "920", "MOTD": "New defaults ignored"},
                              "#!/bin/bash\nexec java -version\n", transport)
            for name, data in state.items():
                self.assertEqual((root / name).read_bytes(), data, name)
            self.assertEqual(calls[0], "https://api.mohistmc.com/project/youer/1.21.1/builds")
            self.assertEqual(calls[1], calls[0] + "/920/download")
            import json
            self.assertEqual(json.loads((root / ".youer/install.json").read_text())["build"], 920)
            self.assertEqual((root / ".youer/start.sh").read_text(), "#!/bin/bash\nexec java -version\n")

    def test_unowned_managed_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".youer").mkdir()
            path = root / ".youer/install.json"
            path.write_text('{"custom": true}')
            calls = []
            def forbidden(url):
                calls.append(url)
                raise AssertionError("Network must not run for an unsafe destination")
            with self.assertRaisesRegex(ValueError, "not owned"):
                installer.install(root, {}, "new runtime", forbidden)
            self.assertEqual(path.read_text(), '{"custom": true}')
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
