import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

from minicode.llm import QwenClient, ModelError


class ClientTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        cwd = patch("minicode.config.Path.cwd", return_value=self.root)
        cwd.start()
        self.addCleanup(cwd.stop)

    def test_loads_dotenv_without_exporting_secrets(self):
        (self.root / ".env").write_text(
            '# config\nexport MINICODE_BASE_URL="https://example.org/v1" # endpoint\n'
            "MINICODE_MODEL='qwen-test'\nMINICODE_API_KEY='test#key'\n",
            encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            client = QwenClient()
            self.assertEqual(client.url, "https://example.org/v1/chat/completions")
            self.assertEqual(client.model, "qwen-test")
            self.assertEqual(client.key, "test#key")
            self.assertNotIn("MINICODE_API_KEY", os.environ)

    def test_explicit_file_and_environment_priority(self):
        path = self.root / "custom.env"
        path.write_text("MINICODE_BASE_URL=https://example.org/v1\nMINICODE_MODEL=file-model\nMINICODE_API_KEY=$(echo-secret)\n")
        with patch.dict(os.environ, {"MINICODE_MODEL": "shell-model"}, clear=True):
            client = QwenClient(path)
            self.assertEqual(client.model, "shell-model")
            self.assertEqual(client.key, "$(echo-secret)")

    def test_missing_explicit_file(self):
        with self.assertRaisesRegex(ValueError, "não encontrado"):
            QwenClient(self.root / "missing.env")

    def test_invalid_dotenv_does_not_leak_secret(self):
        (self.root / ".env").write_text('MINICODE_API_KEY="private-test-secret\n')
        with self.assertRaisesRegex(ValueError, "linha 1") as caught:
            QwenClient()
        self.assertNotIn("private-test-secret", str(caught.exception))

    def test_configuration_and_https(self):
        for env in [{}, {"MINICODE_BASE_URL": "http://remote.example/v1", "MINICODE_MODEL": "qwen"},
                    {"MINICODE_BASE_URL": "https://user:pass@example.org/v1", "MINICODE_MODEL": "qwen"}]:
            with patch.dict(os.environ, env, clear=True), self.assertRaises(ModelError):
                QwenClient()

    def test_payload_and_response(self):
        env = {"MINICODE_BASE_URL": "https://example.org/v1", "MINICODE_MODEL": "qwen", "MINICODE_API_KEY": "test-only"}
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps({"choices": [{"message": {"content": '{"tool":"run_tests"}'}}]}).encode()
        with patch.dict(os.environ, env, clear=True), patch("urllib.request.build_opener", return_value=opener):
            self.assertEqual(json.loads(QwenClient().complete([]))["tool"], "run_tests")
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.org/v1/chat/completions")
        self.assertEqual(json.loads(request.data)["model"], "qwen")
        self.assertEqual(request.headers["Authorization"], "Bearer test-only")

    def test_http_error_does_not_leak_body(self):
        env = {"MINICODE_BASE_URL": "https://example.org/v1", "MINICODE_MODEL": "qwen"}
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError("https://example.org", 401, "secret", {}, None)
        with patch.dict(os.environ, env, clear=True), patch("urllib.request.build_opener", return_value=opener):
            with self.assertRaisesRegex(ModelError, "HTTP 401") as caught:
                QwenClient().complete([])
        self.assertNotIn("secret", str(caught.exception))

    def test_malformed_endpoint_responses_are_model_errors(self):
        env = {'MINICODE_BASE_URL':'https://example.org/v1','MINICODE_MODEL':'qwen'}
        for body in [{'choices':[]},{'choices':None},[],{'choices':[{}]},{'choices':[{'message':{'content':None}}]}]:
            opener = MagicMock()
            opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(body).encode()
            with self.subTest(body=body), patch.dict(os.environ,env,clear=True), patch('urllib.request.build_opener',return_value=opener):
                with self.assertRaises(ModelError):
                    QwenClient().complete([])

    def test_url_without_hostname_is_rejected(self):
        with patch.dict(os.environ,{'MINICODE_BASE_URL':'https:///v1','MINICODE_MODEL':'qwen'},clear=True):
            with self.assertRaises(ModelError):
                QwenClient()
