"""The importer must reject unsafe/corrupt exports before creating a destination."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class TrainingImportTests(unittest.TestCase):
    def run_import(self, extra=None, corrupt=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = b'evidence'
            manifest = {'status': 'fixture', 'artifact_sha256': {
                'result.json': hashlib.sha256(payload).hexdigest()}, 'adapter_files': {}}
            with zipfile.ZipFile(root/'export.zip', 'w') as archive:
                archive.writestr('run/run_manifest.json', json.dumps(manifest))
                archive.writestr('run/result.json', b'changed' if corrupt else payload)
                if extra:
                    archive.writestr(extra, 'unsafe')
            result = subprocess.run([sys.executable, str(ROOT/'scripts/import_training_export.py'),
                str(root/'export.zip'), '--output', str(root/'out')], capture_output=True, text=True)
            return result, (root/'out').exists()

    def test_valid_export_is_imported(self):
        result, exists = self.run_import()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(exists)

    def test_traversal_is_rejected_before_extraction(self):
        result, exists = self.run_import(extra='run/../../escape')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(exists)

    def test_corrupted_evidence_is_rejected_before_extraction(self):
        result, exists = self.run_import(corrupt=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(exists)
