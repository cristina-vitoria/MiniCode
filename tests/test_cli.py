import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from minicode.cli import main

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def test_help_without_model_configuration(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as result:
            main(['--help'])
        self.assertEqual(result.exception.code,0)
        self.assertIn('--test-profile',output.getvalue())

    def test_task_list_has_six_entries_without_client(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output), patch('minicode.cli.QwenClient') as client:
            self.assertEqual(main(['--list-tasks']),0)
        client.assert_not_called()
        self.assertEqual(len(json.loads(output.getvalue())),6)

    def test_prepare_never_overwrites_and_omits_venv(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp)/'project'
            args=['--prepare-task','discount','--source',str(ROOT/'softwareteste'),'--project',str(project)]
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args),0)
                self.assertEqual(main(args),2)
            self.assertTrue((project/'app/cart_service.py').exists())
            self.assertFalse((project/'.venv').exists())

    def test_no_independent_acceptance_is_configuration_error(self):
        with contextlib.redirect_stderr(io.StringIO()), patch('minicode.cli.QwenClient') as client:
            self.assertEqual(main(['--task','Implement something']),2)
        client.assert_not_called()

    def test_limits_checked_before_client(self):
        with contextlib.redirect_stderr(io.StringIO()), patch('minicode.cli.QwenClient') as client:
            self.assertEqual(main(['--max-iterations','0']),2)
        client.assert_not_called()
