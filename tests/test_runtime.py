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
            for key in ("INITIAL_HEAP_MB", "GC_MODE", "EXTRA_JVM_ARGS", "JAVA_TOOL_OPTIONS",
                        "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
                env.pop(key, None)
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
            result = subprocess.run([bash, bash_path(runner), bash_path(SOURCE)], cwd=tmp, env=env, text=True,
                                    input="stop\n", capture_output=True, timeout=10)
            self.assertFalse(Path(tmp, "injected").exists(), "User input executed a shell payload")
            return result

    def test_initial_heap_is_configurable_within_effective_maximum(self):
        for initial in ("16", "256", "5120"):
            with self.subTest(initial=initial):
                result = self.run_runtime({"INITIAL_HEAP_MB": initial})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"<-Xms{initial}M>", result.stdout)
        for initial in ("0", "15", "0512", "5121", "1048577", "1+2", ""):
            with self.subTest(initial=initial):
                result = self.run_runtime({"INITIAL_HEAP_MB": initial})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("INITIAL_HEAP_MB", result.stderr)
                self.assertNotIn("<-jar>", result.stdout)

    def test_gc_selector_maps_only_supported_collectors(self):
        selections = {"default": [], "g1": ["-XX:+UseG1GC"], "zgc": ["-XX:+UseZGC"],
                      "zgc-generational": ["-XX:+UseZGC", "-XX:+ZGenerational"],
                      "parallel": ["-XX:+UseParallelGC"], "serial": ["-XX:+UseSerialGC"]}
        for mode, expected in selections.items():
            with self.subTest(mode=mode):
                result = self.run_runtime({"GC_MODE": mode})
                self.assertEqual(result.returncode, 0, result.stderr)
                flags = [line[1:-1] for line in result.stdout.splitlines() if line.startswith("<-XX:")]
                self.assertEqual(flags, expected)
        for mode in ("", "G1", "shenandoah", "g1; touch injected"):
            with self.subTest(mode=mode):
                result = self.run_runtime({"GC_MODE": mode})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("GC_MODE", result.stderr)
                self.assertNotIn("<-jar>", result.stdout)

    def test_extra_jvm_arguments_use_quotes_and_backslash_without_shell_expansion(self):
        value = r'''  -Dmessage='hello world' -Dquoted="say \"hello\"" -Dpath='C:\mods\test' -Descaped=hello\ world -Dslash=one\\two -Dliteral='$(printf unsafe);`id`|&<>*?${HOME}' -Dempty=""  '''
        result = self.run_runtime({"EXTRA_JVM_ARGS": value})
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = [line[1:-1] for line in result.stdout.splitlines() if line.startswith("<")]
        self.assertEqual(arguments, ["-Xms128M", "-Xmx5120M", "-Dterminal.jline=false",
                                    "-Dterminal.ansi=true", "-Dmessage=hello world", '-Dquoted=say "hello"',
                                    r"-Dpath=C:\mods\test", "-Descaped=hello world", r"-Dslash=one\two",
                                    "-Dliteral=$(printf unsafe);`id`|&<>*?${HOME}", "-Dempty=",
                                    "-jar", "server.jar", "nogui"])

    def test_command_substitution_and_backticks_cannot_create_files(self):
        value = "-Done='$(touch injected)' -Dtwo='`touch injected`' -Dthree='; touch injected'"
        result = self.run_runtime({"EXTRA_JVM_ARGS": value})
        self.assertEqual(result.returncode, 0, result.stderr)

        self.assertIn("<-Done=$(touch injected)>", result.stdout)
        self.assertIn("<-Dtwo=`touch injected`>", result.stdout)
        self.assertIn("<-Dthree=; touch injected>", result.stdout)

    def test_older_environments_produce_exactly_the_previous_argv(self):
        expected = ["<-Xms128M>", "<-Xmx5120M>", "<-Dterminal.jline=false>",
                    "<-Dterminal.ansi=true>", "<-jar>", "<server.jar>", "<nogui>"]
        for extra in ({}, {"EXTRA_JVM_ARGS": ""}, {"EXTRA_JVM_ARGS": "   "},
                      {"JAVA_TOOL_OPTIONS": "", "JDK_JAVA_OPTIONS": "", "_JAVA_OPTIONS": ""}):
            with self.subTest(extra=extra):
                result = self.run_runtime(extra)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([line for line in result.stdout.splitlines() if line.startswith("<")], expected)

    def test_extra_lexer_accepts_the_4096_character_boundary(self):
        value = "-Dvalue=" + "s" * (4096 - len("-Dvalue="))
        result = self.run_runtime({"EXTRA_JVM_ARGS": value})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"<{value}>", result.stdout)

    def test_all_representable_ascii_control_characters_are_blocked(self):
        # NUL cannot be carried in an OS environment; installer validation covers it.
        for codepoint in [*range(1, 32), 127]:
            with self.subTest(codepoint=codepoint):
                result = self.run_runtime({"EXTRA_JVM_ARGS": "-Dsecret=do-not-log" + chr(codepoint)})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("control", result.stderr)
                self.assertNotIn("do-not-log", result.stderr)
                self.assertNotIn("<-jar>", result.stdout)

    def test_extra_jvm_lexer_rejects_malformed_or_unbounded_input_before_java(self):
        for value in ("-Dsecret='do-not-log", '-Dsecret="do-not-log', "-Dsecret=do-not-log\\",
                      "-Dsecret=do-not-log\n", "-Dsecret=do-not-log\t", "-Dsecret=do-not-log\r",
                      "-Dsecret=do-not-log\x7f", "-Dsecret=do-not-log\x01", "-Dsecret=" + "s" * 4088):
            with self.subTest(value=repr(value)):
                result = self.run_runtime({"EXTRA_JVM_ARGS": value})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("EXTRA_JVM_ARGS", result.stderr)
                self.assertNotIn("do-not-log", result.stderr)
                self.assertNotIn("<-jar>", result.stdout)

    def test_extra_jvm_arguments_cannot_replace_the_entrypoint_or_load_option_files(self):
        blocked = ("Main", "-jar other.jar", "-cp lib", "-classpath=lib", "--class-path=lib", "-m app/Main",
                   "--module=app/Main", "-p lib", "--module-path=lib", "--source=21", "--help", "-help", "-h",
                   "-version", "--version", "-fullversion", "-X", "-Xinternalversion", "-Xshare:dump",
                   "-Xlog:help", "-Xbootclasspath/a:lib", "--dry-run", "--list-modules", "@args.txt",
                   "-XX:Flags=options.txt", "-XX:VMOptionsFile=options.txt", "-XX:+PrintFlagsInitial",
                   "-XX:+IgnoreUnrecognizedVMOptions", "--add-opens java.base/java.lang=ALL-UNNAMED",
                   "--unknown=value", "''", "-D", "-XX:", "-Dgood=yes ; touch injected")
        for value in blocked:
            with self.subTest(value=value):
                result = self.run_runtime({"EXTRA_JVM_ARGS": value})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("EXTRA_JVM_ARGS", result.stderr)
                self.assertNotIn("<-jar>", result.stdout)

    def test_extra_jvm_arguments_reserve_heap_and_gc_for_dedicated_fields(self):
        heap = ("-Xmx8G", "-Xms2G", "-XX:MaxHeapSize=8G", "-XX:InitialHeapSize=2G", "-XX:MinHeapSize=2G")
        collectors = ("-XX:+UseG1GC", "-XX:-UseG1GC", "-XX:+UseZGC", "-XX:-UseSerialGC",
                      "-XX:UseParallelGC=true", "-XX:+UseShenandoahGC", "-XX:+ZGenerational",
                      "-XX:-ZGenerational", "-XX:ZGenerational=false")
        for value in heap + collectors:
            with self.subTest(value=value):
                result = self.run_runtime({"EXTRA_JVM_ARGS": value})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("HEAP_MB" if value in heap else "GC_MODE", result.stderr)
                self.assertNotIn("<-jar>", result.stdout)

    def test_supported_tuning_families_and_single_equals_module_options_pass_as_one_argument(self):
        options = ["-Dexample=value", "-XX:+AlwaysPreTouch", "-XX:MaxGCPauseMillis=200", "-Xss1M",
                   "-Xlog:gc*", "-XX:SoftMaxHeapSize=1G", "--add-opens=java.base/java.lang=ALL-UNNAMED",
                   "--add-exports=java.base/jdk.internal.misc=ALL-UNNAMED", "--add-reads=java.base=ALL-UNNAMED",
                   "--enable-native-access=ALL-UNNAMED"]
        result = self.run_runtime({"EXTRA_JVM_ARGS": " ".join(options)})
        self.assertEqual(result.returncode, 0, result.stderr)
        for option in options:
            self.assertIn(f"<{option}>", result.stdout)

    def test_hidden_jvm_environment_options_fail_closed_instead_of_overriding_egg_fields(self):
        for name in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
            with self.subTest(name=name):
                result = self.run_runtime({name: "-Xmx8G -Dsecret=do-not-log"})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(name, result.stderr)
                self.assertIn("Egg", result.stderr)
                self.assertNotIn("do-not-log", result.stderr)
                self.assertNotIn("<-jar>", result.stdout)

    def test_print_flags_with_comments_cannot_turn_server_start_into_exit_only_command(self):
        result = self.run_runtime({"EXTRA_JVM_ARGS": "-XX:+PrintFlagsWithComments"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EXTRA_JVM_ARGS", result.stderr)
        self.assertNotIn("<-jar>", result.stdout)

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
