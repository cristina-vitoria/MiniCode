import json
import os
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

from minicode.llm import QwenClient, ModelError


class ClientTests(unittest.TestCase):
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
