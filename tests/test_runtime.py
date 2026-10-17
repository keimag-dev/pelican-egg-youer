import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "runtime.sh"
SCRATCH = Path(tempfile.gettempdir())


class RuntimeTests(unittest.TestCase):
    def run_runtime(self, overrides=None):
        with tempfile.TemporaryDirectory(dir=SCRATCH, ignore_cleanup_errors=True) as tmp:
            Path(tmp, "server.jar").write_bytes(b"placeholder")
            env = os.environ.copy()
            env.update({"SERVER_MEMORY": "6144", "HEAP_MB": "0", "NATIVE_HEADROOM_MB": "1024",
                        "UNLIMITED_HEAP_MB": "4096", "SERVER_JARFILE": "server.jar"})
            env.update(overrides or {})
            runner = Path(tmp, "runner.sh")
            runner.write_text('export PATH="$(dirname "$0")/bin:$PATH"\nbash "$1"\n', encoding="utf-8")
            binary = Path(tmp, "bin/java")
            binary.parent.mkdir()
            binary.write_text('#!/bin/bash\nprintf "<%s>\\n" "$@"\nif [[ ${JAVA_READ_STDIN:-0} == 1 ]]; then IFS= read -r command; printf "console:%s\\n" "$command"; fi\nexit "${JAVA_EXIT:-0}"\n', encoding="utf-8")
            binary.chmod(0o755)
            def bash_path(path):
                value = path.as_posix()
                return "/" + value[0].lower() + value[2:] if os.name == "nt" else value
            bash = shutil.which("bash")
            if bash is None:
                self.fail("Bash is required to exercise the real runtime wrapper")
            return subprocess.run([bash, bash_path(runner), bash_path(SOURCE)], cwd=tmp, env=env, text=True,
                                  input="stop\n", capture_output=True, timeout=10)

    def test_bounded_heap_and_exit_code_propagate_without_python(self):
        result = self.run_runtime({"JAVA_EXIT": "37"})
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertIn("<-Xmx5120M>", result.stdout)
        self.assertIn("<-Xms128M>", result.stdout)
        self.assertIn("<server.jar>", result.stdout)
        self.assertIn("<nogui>", result.stdout)

    def test_console_stdin_is_delivered_to_executed_process(self):
        result = self.run_runtime({"JAVA_READ_STDIN": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("console:stop", result.stdout)

    def test_heap_policy_unlimited_explicit_and_invalid_parameters(self):
        for env, expected in (({"SERVER_MEMORY": "0"}, "4096"),
                              ({"HEAP_MB": "2048"}, "2048"),
                              ({"SERVER_MEMORY": "0", "HEAP_MB": "3072"}, "3072")):
            with self.subTest(env=env):
                result = self.run_runtime(env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"<-Xmx{expected}M>", result.stdout)
        for env in ({"SERVER_JARFILE": "$(touch injected).jar"}, {"SERVER_JARFILE": "../x.jar"},
                    {"HEAP_MB": "6000"}, {"HEAP_MB": "100"}, {"HEAP_MB": "0+1"},
                    {"HEAP_MB": "010"}, {"SERVER_MEMORY": "1024"},
                    {"SERVER_MEMORY": "10000000000000000000000000000000"},
                    {"NATIVE_HEADROOM_MB": "0"}, {"UNLIMITED_HEAP_MB": "1"}):
            with self.subTest(env=env):
                result = self.run_runtime(env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ERROR:", result.stderr)
                self.assertNotIn("<-jar>", result.stdout)


if __name__ == "__main__":
    unittest.main()
