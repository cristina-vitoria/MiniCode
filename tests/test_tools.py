import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
import subprocess
import sys

from minicode.tools import TestRunner, ToolError, Workspace


class ToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tests").mkdir()
        (self.root / "tests/test_original.py").write_text("# original")
        self.ws = Workspace(self.root)

    def test_paths_and_sensitive_files(self):
        for path in ["../outside", "/etc/passwd", ".env", ".git/config", "a/.minicode/x", "key.pem"]:
            with self.subTest(path=path), self.assertRaises(ToolError): self.ws.write_file(path, "bad")
        self.assertFalse((self.root / ".env").exists())

    def test_links_rejected(self):
        (self.root / "link").symlink_to("/tmp", target_is_directory=True)
        with self.assertRaises(ToolError): self.ws.write_file("link/x", "bad")
        original = self.root / "original"
        original.write_text("data")
        os.link(original, self.root / "hard")
        with self.assertRaises(ToolError): self.ws.write_file("hard", "bad")
        self.assertEqual(original.read_text(), "data")

    def test_protected_tests_and_new_tests(self):
        with self.assertRaises(ToolError): self.ws.write_file("tests/test_original.py", "pass")
        self.ws.write_file("tests/test_new.py", "# new")
        self.assertEqual(self.ws.revision, 1)
        self.assertIn("tests/test_new.py", self.ws.changed)

    def test_search_read_and_size_limit(self):
        self.ws.write_file("src/app.py", "answer = 42\n")
        self.assertEqual(self.ws.search_code("answer")[0]["line"], 1)
        self.assertEqual(self.ws.read_file("src/app.py"), "answer = 42\n")
        with self.assertRaises(ToolError): self.ws.write_file("huge.py", "x" * 40001)

    def test_empty_suite_is_failure(self):
        result = TestRunner(self.root, "local").run()
        self.assertFalse(result["passed"])
        self.assertEqual(result["tests"], 0)

    def test_timeout(self):
        (self.root / "tests/test_sleep.py").write_text("import time\ntime.sleep(20)\n")
        result = TestRunner(self.root, "local", 1).run()
        self.assertFalse(result["passed"])
        self.assertTrue(result["timed_out"])

    def test_secrets_not_in_child_environment(self):
        (self.root / "tests/test_env.py").write_text("import unittest, os\nclass Env(unittest.TestCase):\n    def test_key(self):\n        self.assertNotIn('MINICODE_API_KEY', os.environ)\n")
        with patch.dict(os.environ, {"MINICODE_API_KEY": "dummy-test-secret"}):
            self.assertTrue(TestRunner(self.root, "local").run()["passed"])

    def test_skipped_suite_is_not_success(self):
        (self.root / "tests/test_skip.py").write_text("import unittest\nclass Skip(unittest.TestCase):\n    @unittest.skip('not implemented')\n    def test_skip(self): pass\n")
        result = TestRunner(self.root, "local").run()
        self.assertFalse(result["passed"])
        self.assertEqual(result["tests"], 0)
        self.assertEqual(result["discovered"], 1)

    def test_aliases_cannot_overwrite_original_tests(self):
        for path in ['tests/test_original.py','./tests/test_original.py','tests//test_original.py','tests/./test_original.py']:
            with self.subTest(path=path), self.assertRaises(ToolError):
                self.ws.write_file(path,'replaced')

    def test_protection_is_not_limited_to_first_thousand_files(self):
        for i in range(1001):
            (self.root / f'a{i:04}.txt').write_text('data')
        ws = Workspace(self.root)
        self.assertNotIn('tests/test_original.py',ws.list_files())
        with self.assertRaises(ToolError):
            ws.write_file('tests/test_original.py','replaced')

    def test_original_test_changed_outside_tool_is_rejected(self):
        runner = TestRunner(self.root,'local')
        (self.root/'tests/test_original.py').write_text('changed')
        result = runner.run()
        self.assertFalse(result['passed'])
        self.assertIn('protegido',result['error'])

    def test_framework_shadowing_is_rejected(self):
        with self.assertRaises(ToolError):
            self.ws.write_file('unittest.py','print("Ran 1 test in 0.001s")')
        (self.root/'unittest.py').write_text('print("Ran 1 test in 0.001s\\nOK")')
        result = TestRunner(self.root,'local').run()
        self.assertFalse(result['passed'])
        self.assertFalse(result['verified'])

    def test_forged_stdout_and_early_exit_are_not_reports(self):
        (self.root/'tests/test_fake.py').write_text(
            'import os\nprint("Ran 1 test in 0.001s\\nOK", flush=True)\nos._exit(0)\n')
        result = TestRunner(self.root,'local').run()
        self.assertEqual(result['returncode'],0)
        self.assertFalse(result['verified'])
        self.assertFalse(result['passed'])

    def test_long_output_keeps_counts_and_full_log(self):
        (self.root/'tests/test_verbose.py').write_text(
            'import unittest\nprint("x"*17000,flush=True)\nclass T(unittest.TestCase):\n'
            '    def test_ok(self): self.assertTrue(True)\n')
        result = TestRunner(self.root,'local').run()
        self.assertTrue(result['passed'])
        self.assertEqual(result['tests'],1)
        self.assertGreater(len(result['output']),17000)

    def test_snapshot_omits_hidden_and_sensitive_files(self):
        (self.root/'.env').write_text('DUMMY_SECRET=not-real')
        (self.root/'secrets.json').write_text('{}')
        (self.root/'tests/test_filtered.py').write_text(
            'import unittest\nfrom pathlib import Path\nclass T(unittest.TestCase):\n'
            '    def test_files(self):\n'
            '        self.assertFalse(Path(".env").exists())\n'
            '        self.assertFalse(Path("secrets.json").exists())\n')
        result = TestRunner(self.root,'local').run()
        self.assertTrue(result['passed'],result)
        self.assertNotIn('DUMMY_SECRET',result['output'])

    def test_missing_independent_report_never_passes(self):
        (self.root/'tests/test_ok.py').write_text('import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n')
        with tempfile.TemporaryDirectory() as tmp:
            oracle = Path(tmp)/'tests'; oracle.mkdir()
            (oracle/'test_failure.py').write_text('import unittest\nclass T(unittest.TestCase):\n    def test_no(self): self.fail("independent failure")\n')
            result = TestRunner(self.root,'local',acceptance_dir=oracle).run()
        self.assertFalse(result['passed'])
        self.assertIn('independent failure',result['acceptance']['output'])

    def test_keyboard_interrupt_kills_child(self):
        (self.root/'tests/test_sleep.py').write_text('import time\ntime.sleep(20)\n')
        processes = []
        real_popen = subprocess.Popen
        def start(*args,**kwargs):
            child = real_popen(*args,**kwargs)
            processes.append(child)
            return child
        with patch('minicode.tools.subprocess.Popen',side_effect=start), patch('minicode.tools.time.sleep',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                TestRunner(self.root,'local').run()
        self.assertIsNotNone(processes[0].poll())
