"""Integração opcional: MINICODE_DOCKER_TESTS=1 python -m unittest discover -s tests -p test_docker.py -v."""
import os
from pathlib import Path
import tempfile
import unittest

from minicode.tools import TestRunner
from minicode.workspace import copy_filtered
from minicode.tasks import TASKS, TaskAcceptance

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('MINICODE_DOCKER_TESTS') == '1','Docker opt-in')
class DockerTests(unittest.TestCase):
    def test_softwareteste_pytest_in_container(self):
        result=TestRunner(ROOT/'softwareteste',profile='pytest',timeout=30).run()
        self.assertTrue(result['passed'],result)
        self.assertEqual(result['tests'],16)

    def test_no_network_secrets_or_project_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'project';(root/'tests').mkdir(parents=True)
            (root/'.env').write_text('DUMMY_SECRET=not-real')
            (root/'tests/test_isolation.py').write_text('''import unittest
from pathlib import Path
import socket
class Isolation(unittest.TestCase):
    def test_isolation(self):
        self.assertFalse(Path('.env').exists())
        with self.assertRaises(OSError): Path('outside.txt').write_text('blocked')
        with self.assertRaises(OSError): socket.create_connection(('1.1.1.1',443),timeout=1)
''')
            result=TestRunner(root,timeout=10).run()
            self.assertTrue(result['passed'],result)
            self.assertFalse((root/'outside.txt').exists())

    def test_forged_stdout_in_container_is_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'tests').mkdir()
            (root/'tests/test_exit.py').write_text('import os\nprint("Ran 1 test in 0.1s\\nOK",flush=True)\nos._exit(0)\n')
            result=TestRunner(root).run()
            self.assertFalse(result['passed'])
            self.assertFalse(result['verified'])

    def test_independent_oracle_in_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'project';copy_filtered(ROOT/'softwareteste',root)
            (root/'app/cart_service.py').write_bytes((ROOT/'tests/fixtures/discount.py').read_bytes())
            (root/'tests/test_cart_service.py').write_text('def test_smoke(): assert True\n')
            result=TaskAcceptance(TASKS[0],ROOT/'softwareteste',timeout=30)(root)
            self.assertTrue(result['passed'],result)
