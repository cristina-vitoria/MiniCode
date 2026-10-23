import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
