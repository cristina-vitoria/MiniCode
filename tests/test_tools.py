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

    def test_rejects_invalid_python_and_noop_writes(self):
        with self.assertRaisesRegex(ToolError, "Python inválido"):
            self.ws.write_file("broken.py", 'def broken(:\n')
        self.ws.write_file("valid.py", "answer = 42\n")
        with self.assertRaisesRegex(ToolError, "sem alteração"):
            self.ws.write_file("valid.py", "answer = 42\n")
        self.assertEqual(self.ws.revision, 1)

    def test_normalizes_accidentally_double_escaped_python_newlines(self):
        result = self.ws.write_file(
            "tests/test_new.py", "def test_one(): pass\\n\\ndef test_two(): pass\n")
        self.assertTrue(result["normalized_escaped_newlines"])
        self.assertIn("\n\ndef test_two", self.ws.read_file("tests/test_new.py"))

    def test_replace_text_requires_one_match_and_valid_result(self):
        self.ws.write_file("calculation.py", "divisor = 1000\n")
        result = self.ws.replace_text("calculation.py", "1000", "100")
        self.assertEqual(self.ws.read_file("calculation.py"), "divisor = 100\n")
        self.assertEqual(result["revision"], 2)
        with self.assertRaisesRegex(ToolError, "encontradas: 0"):
            self.ws.replace_text("calculation.py", "missing", "value")
        with self.assertRaisesRegex(ToolError, "Python inválido"):
            self.ws.replace_text("calculation.py", "divisor = 100", "def broken(")

    def test_can_freeze_new_tests_after_first_verification(self):
        self.ws.write_file("tests/test_new.py", "def test_new(): pass\n")
        self.assertEqual(self.ws.protect_current_tests(), ["tests/test_new.py"])
        with self.assertRaisesRegex(ToolError, "Teste congelado"):
            self.ws.write_file("tests/test_new.py", "def test_new(): assert True\n")
        self.assertEqual(self.ws.protect_current_tests(), [])
        self.assertEqual(self.ws.unprotect_generated_tests(), ["tests/test_new.py"])
        self.ws.write_file("tests/test_new.py", "def test_new(): assert True\n")
        with self.assertRaisesRegex(ToolError, "protegidos"):
            self.ws.write_file("tests/test_original.py", "def test_original(): assert True\n")

    def test_search_read_and_size_limit(self):
        self.ws.write_file("src/app.py", "answer = 42\n")
        self.assertEqual(self.ws.search_code("answer")[0]["line"], 1)
        self.assertEqual(self.ws.read_file("src/app.py"), "answer = 42\n")
        with self.assertRaises(ToolError): self.ws.write_file("huge.py", "x" * 40001)

    def test_write_scope_rejects_files_outside_task(self):
        (self.root / "app.py").write_text("VALUE = 1\n")
        scoped = Workspace(self.root, editable_paths={"tests/test_new.py"})
        scoped.write_file("tests/test_new.py", "def test_new(): pass\n")
        with self.assertRaisesRegex(ToolError, "fora do escopo"):
            scoped.write_file("app.py", "VALUE = 2\n")

    def test_original_python_api_cannot_be_removed(self):
        (self.root / "module.py").write_text(
            "import math\n\ndef health(): return True\n\ndef target(): return math.pi\n")
        workspace = Workspace(self.root)
        with self.assertRaisesRegex(ToolError, "remove ou altera APIs/imports"):
            workspace.write_file("module.py", "def target(): return 3\n")
        workspace.replace_text("module.py", "return math.pi", "return math.tau")

    def test_original_function_signature_cannot_be_changed(self):
        (self.root / "module.py").write_text(
            "def calculate(value: int, rate: int = 1) -> int:\n    return value * rate\n")
        workspace = Workspace(self.root)
        with self.assertRaisesRegex(ToolError, "remove ou altera APIs/imports"):
            workspace.replace_python_function(
                "module.py", "calculate",
                "def calculate(value: int, rate: float = 1) -> int:\n    return int(value * rate)\n")
        workspace.replace_text("module.py", "return value * rate", "return value * rate // 1")

    def test_replace_python_function_is_local_and_preserves_other_functions(self):
        (self.root / "module.py").write_text(
            "def health(): return True\n\ndef target():\n    return 1\n")
        workspace = Workspace(self.root)
        workspace.replace_python_function("module.py", "target", "def target():\n    return 2\n")
        self.assertEqual(workspace.read_file("module.py"),
                         "def health(): return True\n\ndef target():\n    return 2\n")
        with self.assertRaisesRegex(ToolError, "função alvo"):
            workspace.replace_python_function("module.py", "target", "def renamed(): return 3\n")

    def test_replace_python_function_can_add_helpers_and_normalize_newlines(self):
        (self.root / "module.py").write_text(
            "def health(): return True\n\ndef target(value):\n    return value\n")
        workspace = Workspace(self.root)
        result = workspace.replace_python_function(
            "module.py", "target",
            "def helper(value): return value * 2\\n\\ndef target(value): return helper(value)\n")
        self.assertTrue(result["normalized_escaped_newlines"])
        content = workspace.read_file("module.py")
        self.assertIn("def health()", content)
        self.assertIn("def helper(value)", content)
        self.assertIn("def target(value)", content)
        self.assertEqual(content.count("def target"), 1)

    def test_new_local_import_cycle_is_rejected(self):
        package = self.root / "app"
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "a.py").write_text("from .b import value\n")
        (package / "b.py").write_text("value = 1\n")
        workspace = Workspace(self.root)
        with self.assertRaisesRegex(ToolError, "Import circular"):
            workspace.write_file("app/b.py", "from .a import value\n")

    def test_accepted_production_can_be_frozen(self):
        (self.root / "app.py").write_text("VALUE = 1\n")
        workspace = Workspace(self.root)
        workspace.write_file("app.py", "VALUE = 2\n")
        self.assertEqual(workspace.protect_changed_production(), ["app.py"])
        with self.assertRaisesRegex(ToolError, "Produção aprovada"):
            workspace.write_file("app.py", "VALUE = 3\n")

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
