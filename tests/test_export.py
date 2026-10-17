import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import build_egg
import installer


class ExportTests(unittest.TestCase):
    def test_jvm_tuning_defaults_are_exposed_with_ui_validation(self):
        variables = {v["env_variable"]: v for v in build_egg.export_egg()["variables"]}
        self.assertIn("-Xmx", variables["HEAP_MB"]["name"])
        expected = {"INITIAL_HEAP_MB": "128", "GC_MODE": "default", "EXTRA_JVM_ARGS": ""}
        for key, default in expected.items():
            with self.subTest(key=key):
                self.assertEqual(installer.DEFAULTS.get(key), default)
                self.assertIn(key, variables)
                self.assertEqual(variables[key]["default_value"], default)
        self.assertIn("-Xms", variables["INITIAL_HEAP_MB"]["name"])
        self.assertIn("between:16,1048576", variables["INITIAL_HEAP_MB"]["rules"])
        self.assertIn("in:default,g1,zgc,zgc-generational,parallel,serial", variables["GC_MODE"]["rules"])
        self.assertIn("nullable", variables["EXTRA_JVM_ARGS"]["rules"])
        self.assertIn("max:4096", variables["EXTRA_JVM_ARGS"]["rules"])
        self.assertIn(r"not_regex:/[\x00-\x1f\x7f]/", variables["EXTRA_JVM_ARGS"]["rules"])

    def test_startup_replaces_image_shell_for_signal_delivery(self):
        self.assertTrue(build_egg.export_egg()["startup_commands"]["Default"].startswith("exec "),
                        "Image entrypoint shell must hand off to the Java supervisor")

    def test_standalone_native_export_matches_embedded_sources(self):
        egg = build_egg.export_egg()
        self.assertEqual(egg["meta"], {"version": "PLCN_v3", "update_url": None})
        self.assertIn("Permission is hereby granted", egg["_comment"])
        self.assertIn("Copyright (c) 2026 keimag-dev", egg["_comment"])
        self.assertNotIn("startup", egg)
        self.assertEqual(egg["startup_commands"], {"Default": "exec bash .youer/start.sh"})
        self.assertIsInstance(egg["config"]["files"], dict)
        self.assertEqual(egg["config"]["stop"], "stop")
        self.assertIn("eula", egg["features"])
        script = egg["scripts"]["installation"]["script"]
        self.assertIn((BASE / "installer.py").read_text(encoding="utf-8"), script)
        self.assertIn(repr((BASE / "runtime.sh").read_text(encoding="utf-8")), script)
        self.assertNotIn("eval ", script)
        variables = {v["env_variable"]: v for v in egg["variables"]}
        self.assertEqual({k: v["default_value"] for k, v in variables.items()}, installer.DEFAULTS)
        for variable in variables.values():
            self.assertIsInstance(variable["rules"], list)
            self.assertIsInstance(variable["sort"], int)
            self.assertTrue(variable["user_viewable"])
            self.assertTrue(variable["user_editable"])
        for key in ("GAMEMODE", "DIFFICULTY", "ONLINE_MODE", "WHITELIST"):
            self.assertTrue(any(rule.startswith("in:") for rule in variables[key]["rules"]))
        # Exercise the real CLI without overwriting the published update URL in the checkout.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("build_egg.py", "installer.py", "runtime.sh", "LICENSE"):
                shutil.copyfile(BASE / name, root / name)
            shutil.copytree(BASE / "assets", root / "assets")
            output = subprocess.run([sys.executable, str(root / "build_egg.py")],
                                    capture_output=True, text=True)
            self.assertEqual(output.returncode, 0, output.stderr)
            self.assertEqual(json.loads((root / "egg-youer.json").read_text(encoding="utf-8")), egg)
        self.assertEqual(build_egg.export_egg(), egg)

    def test_update_url_is_explicit_opt_in_and_must_use_https(self):
        url = "https://example.test/published/egg-youer.json"
        self.assertEqual(build_egg.export_egg(update_url=url)["meta"]["update_url"], url)
        self.assertIsNone(build_egg.export_egg()["meta"]["update_url"])
        for url in ("http://example.test/egg.json", "file:///egg.json", "not-a-url", "https://"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                build_egg.export_egg(update_url=url)


if __name__ == "__main__":
    unittest.main()
