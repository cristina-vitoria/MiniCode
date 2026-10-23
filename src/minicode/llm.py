"""Cliente HTTP compatível com Chat Completions; sem SDK ou credenciais em disco."""
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse


class ModelError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ModelError("Redirecionamento do endpoint recusado")


class QwenClient:
    def __init__(self):
        base = os.environ.get("MINICODE_BASE_URL", "").rstrip("/")
        self.model = os.environ.get("MINICODE_MODEL", "")
        self.key = os.environ.get("MINICODE_API_KEY", "")
        parsed = urlparse(base)
        if not base or not self.model:
            raise ModelError("Defina MINICODE_BASE_URL e MINICODE_MODEL")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}):
            raise ModelError("Use HTTPS (HTTP permitido apenas em localhost)")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ModelError("URL deve conter somente endereço e caminho, sem credenciais")
        self.url = base + "/chat/completions"

    def complete(self, messages):
        payload = {"model": self.model, "messages": messages, "temperature": 0.1,
                   "max_tokens": 4096}
        request = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.key})
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=90) as response:
                body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise ModelError("Resposta excede limite")
            content = json.loads(body)["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError()
            return content
        except urllib.error.HTTPError as exc:
            raise ModelError(f"Endpoint retornou HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError, TypeError):
            raise ModelError("Falha de conexão ou resposta inválida do endpoint") from None


def parse_object(text):
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Resposta deve ser objeto JSON")
    return value
