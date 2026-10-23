"""Configuração local sem executar shell nem alterar o ambiente do processo."""
import os
from pathlib import Path
import shlex


KEYS = {"MINICODE_BASE_URL", "MINICODE_MODEL", "MINICODE_API_KEY"}


def read_config(env_file=None):
    path = Path(env_file) if env_file is not None else Path.cwd() / ".env"
    values = {}
    try:
        content = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        if env_file is not None:
            raise ValueError("Arquivo informado em --env-file não encontrado") from None
        content = ""
    except (OSError, UnicodeError):
        raise ValueError("Não foi possível ler o arquivo de configuração .env") from None
    for number, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, raw = line.partition("=")
        key = key.strip()
        if key not in KEYS:
            continue
        try:
            parts = shlex.split(raw, comments=True, posix=True)
        except ValueError:
            raise ValueError(f"Valor inválido no .env, linha {number}; confira as aspas") from None
        if not separator or len(parts) > 1:
            raise ValueError(f"Formato inválido no .env, linha {number}; use CHAVE=valor e aspas para espaços")
        values[key] = parts[0] if parts else ""
    # Variáveis exportadas têm prioridade, inclusive quando explicitamente vazias.
    values.update({key: os.environ[key] for key in KEYS if key in os.environ})
    return values
