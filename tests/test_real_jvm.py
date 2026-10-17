"""Real Java21 acceptance: a tiny generated probe JAR, never Minecraft.

Set REQUIRE_REAL_JAVA=1 in CI so missing/wrong Java cannot silently skip.
JAVA21_HOME may point to a portable JRE; javac --release21 can come from a
newer local JDK. No automatic download or system configuration is performed.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HIDDEN_OPTIONS = ('JAVA_TOOL_OPTIONS', 'JDK_JAVA_OPTIONS', '_JAVA_OPTIONS')
PROBE = r'''
import java.lang.management.ManagementFactory;
import com.sun.management.HotSpotDiagnosticMXBean;
import java.io.BufferedReader;
import java.io.InputStreamReader;
public class Probe {
    public static void main(String[] args) throws Exception {
        var vm = ManagementFactory.getPlatformMXBean(HotSpotDiagnosticMXBean.class);
        for (String name : new String[]{"MaxHeapSize", "InitialHeapSize", "UseG1GC",
                "UseZGC", "ZGenerational", "UseParallelGC", "UseSerialGC"}) {
            System.out.println("PROBE " + name + "=" + vm.getVMOption(name).getValue());
        }
        System.out.println("PROBE property=" + System.getProperty("youer.probe", ""));
        System.out.println("PROBE stdin=" + new BufferedReader(new InputStreamReader(System.in)).readLine());
        System.exit(37);
    }
}
'''


def bash_path(path):
    value = Path(path).as_posix()
    return '/' + value[0].lower() + value[2:] if os.name == 'nt' else value


class RealJvmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = dict(os.environ)
        for name in HIDDEN_OPTIONS:
            env.pop(name, None)
        home = os.environ.get('JAVA21_HOME') or os.environ.get('JAVA_HOME')
        suffix = '.exe' if os.name == 'nt' else ''
        java = str(Path(home) / ('bin/java' + suffix)) if home else shutil.which('java')
        javac = shutil.which('javac')
        reason = None
        if not java or not Path(java).is_file() or not javac:
            reason = 'Real Java21 and javac are required for this acceptance test'
        else:
            version = subprocess.run([java, '-version'], capture_output=True, text=True, env=env, timeout=15)
            if version.returncode or not re.search(r'version "21(?:\.|\")', version.stdout + version.stderr):
                reason = 'Real Java21 required; a different Java major is not compatibility evidence'
        if reason:
            if os.environ.get('REQUIRE_REAL_JAVA') == '1':
                raise RuntimeError(reason)
            raise unittest.SkipTest(reason)
        assert java is not None and javac is not None
        bash = shutil.which('bash')
        if bash is None:
            raise RuntimeError('Bash is required for the real runtime acceptance test')
        cls.java, cls.javac, cls.env, cls.bash = java, javac, env, bash
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        source = cls.work / 'Probe.java'
        source.write_text(PROBE, encoding='utf-8', newline='\n')
        result = subprocess.run([javac, '--release', '21', str(source)], cwd=cls.work,
                                capture_output=True, text=True, env=env, timeout=30)
        if result.returncode:
            raise RuntimeError('Probe compilation failed: ' + result.stderr)
        with zipfile.ZipFile(cls.work / 'server.jar', 'w') as jar:
            jar.writestr('META-INF/MANIFEST.MF', 'Manifest-Version: 1.0\nMain-Class: Probe\n\n')
            jar.write(cls.work / 'Probe.class', 'Probe.class')
        binary = cls.work / 'bin/java'
        binary.parent.mkdir()
        binary.write_text('#!/bin/bash\nexec "$REAL_JAVA" "$@"\n', encoding='utf-8', newline='\n')
        binary.chmod(0o755)
        runner = cls.work / 'runner.sh'
        runner.write_text('export PATH="$(dirname "$0")/bin:$PATH"\nexec bash "$1"\n',
                          encoding='utf-8', newline='\n')
        cls.runner = runner

    def test_real_java21_heap_collector_quoted_property_stdin_and_exit(self):
        expected = {'default': None, 'g1': 'UseG1GC', 'zgc': 'UseZGC',
                    'zgc-generational': 'UseZGC', 'parallel': 'UseParallelGC', 'serial': 'UseSerialGC'}
        for mode, flag in expected.items():
            with self.subTest(gc_mode=mode):
                env = dict(self.env, REAL_JAVA=Path(self.java).as_posix(), SERVER_MEMORY='2048',
                           HEAP_MB='512', INITIAL_HEAP_MB='128', NATIVE_HEADROOM_MB='1024',
                           UNLIMITED_HEAP_MB='4096', SERVER_JARFILE='server.jar', GC_MODE=mode,
                           EXTRA_JVM_ARGS='-Dyouer.probe="hello world"')
                result = subprocess.run([self.bash, bash_path(self.runner), bash_path(ROOT / 'runtime.sh')],
                                        cwd=self.work, env=env, input='probe-command\n', capture_output=True,
                                        text=True, timeout=30)
                self.assertEqual(result.returncode, 37, result.stdout + result.stderr)
                values = dict(line.removeprefix('PROBE ').split('=', 1)
                              for line in result.stdout.splitlines() if line.startswith('PROBE '))
                self.assertEqual(values['MaxHeapSize'], str(512 * 1024 * 1024))
                self.assertEqual(values['InitialHeapSize'], str(128 * 1024 * 1024))
                if flag:
                    self.assertEqual(values[flag], 'true')
                if mode in ('zgc', 'zgc-generational'):
                    self.assertEqual(values['ZGenerational'], str(mode == 'zgc-generational').lower())
                self.assertEqual(values['property'], 'hello world')
                self.assertEqual(values['stdin'], 'probe-command')


if __name__ == '__main__':
    unittest.main()
