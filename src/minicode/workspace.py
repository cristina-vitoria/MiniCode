"""Política única de caminhos, integridade dos testes e snapshots filtrados."""
import hashlib
import os
from pathlib import Path
import stat
import sys


class ToolError(ValueError):
    pass


IGNORED_DIRS = {"__pycache__", "node_modules", "venv", "build", "dist"}
SENSITIVE_NAMES = {"credentials", "secrets.json", "secrets.yaml", "secrets.yml", "id_rsa", "id_ed25519"}
CONTROL_FILES = {"conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini"}
RESERVED_MODULES = set(sys.stdlib_module_names) | {"pytest", "_pytest", "pluggy", "sitecustomize", "usercustomize"}


class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ToolError("Projeto deve ser diretório")
        self.revision = 0
        self.changed = set()
        # Sem o limite de apresentação de list_files: todos os testes são protegidos.
        self.original_tests = {name for name in self.files() if self.is_test(name)}
        self.protected = {name: self.hash_file(name) for name in self.files()
                          if self.is_test(name) or Path(name).name in CONTROL_FILES}

    @staticmethod
    def is_test(name):
        p = Path(name)
        return "tests" in p.parts or p.name.startswith("test_") or p.name.endswith("_test.py")

    def path(self, name, write=False):
        if not isinstance(name, str) or not name:
            raise ToolError("Caminho deve ser texto não vazio")
        p = Path(name)
        if p.is_absolute() or ".." in p.parts or not p.parts:
            raise ToolError("Caminho deve ser relativo e interno ao projeto")
        if any(part.startswith(".") or part in IGNORED_DIRS for part in p.parts):
            raise ToolError("Diretório oculto ou reservado")
        if p.suffix.lower() in {".pem", ".key", ".p12", ".pfx"} or p.name.lower() in SENSITIVE_NAMES:
            raise ToolError("Arquivo sensível")
        current = self.root
        for part in p.parts:
            current /= part
            if current.is_symlink():
                raise ToolError("Links simbólicos não são permitidos")
        resolved = current.resolve()
        if not resolved.is_relative_to(self.root):
            raise ToolError("Caminho fora do projeto")
        if current.exists():
            info = current.stat()
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise ToolError("Arquivo especial não permitido")
            if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
                raise ToolError("Hard links não são permitidos")
        canonical = resolved.relative_to(self.root).as_posix()
        if write:
            if canonical in self.protected or p.name in CONTROL_FILES:
                raise ToolError("Testes preexistentes e configuração do runner são protegidos")
            if Path(canonical).parts[0].removesuffix(".py") in RESERVED_MODULES:
                raise ToolError("Nome reservado ao interpretador ou framework de testes")
        return current

    def files(self):
        """Inventário completo; ignora segredos, rejeita links e arquivos especiais."""
        for folder, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in IGNORED_DIRS)
            for d in dirs:
                if (Path(folder) / d).is_symlink():
                    raise ToolError("Link simbólico no projeto")
            for filename in sorted(files):
                name = (Path(folder) / filename).relative_to(self.root).as_posix()
                if any(part.startswith(".") for part in Path(name).parts):
                    continue
                if Path(name).suffix.lower() in {".pem", ".key", ".p12", ".pfx"} or filename.lower() in SENSITIVE_NAMES:
                    continue
                self.path(name)
                yield name

    def list_files(self):
        from itertools import islice
        return list(islice(self.files(), 1000))

    def hash_file(self, name):
        return hashlib.sha256(self.path(name).read_bytes()).hexdigest()

    def manifest(self):
        return {name: self.hash_file(name) for name in self.files()}

    def digest(self):
        import json
        return hashlib.sha256(json.dumps(self.manifest(), sort_keys=True).encode()).hexdigest()

    def verify_protected(self):
        for name, expected in self.protected.items():
            try:
                actual = self.hash_file(name)
            except OSError as exc:
                raise ToolError(f"Arquivo protegido removido: {name}") from exc
            if actual != expected:
                raise ToolError(f"Arquivo protegido alterado: {name}")

    def read_file(self, path):
        p = self.path(path)
        if p.stat().st_size > 40_000:
            raise ToolError("Arquivo excede 40 KB; divida-o antes de usar MiniCode")
        return p.read_text(encoding="utf-8")

    def write_file(self, path, content):
        if not isinstance(content, str) or len(content.encode()) > 40_000:
            raise ToolError("Conteúdo inválido ou maior que 40 KB")
        p = self.path(path, write=True)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        name = p.resolve().relative_to(self.root).as_posix()
        self.revision += 1
        self.changed.add(name)
        return {"path": name, "revision": self.revision, "sha256": self.hash_file(name)}

    def search_code(self, query):
        if not isinstance(query, str) or not query:
            raise ToolError("Busca vazia")
        result = []
        for name in self.files():
            try:
                for n, line in enumerate(self.read_file(name).splitlines(), 1):
                    if query in line:
                        result.append({"path": name, "line": n, "text": line[:300]})
                    if len(result) == 50:
                        return result
            except (OSError, UnicodeError, ToolError):
                continue
        return result


def copy_filtered(source, destination):
    """Copia apenas arquivos autorizados, nunca .env/.git/.minicode/venvs/links."""
    workspace = Workspace(source)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    total = 0
    for name in workspace.files():
        data = workspace.path(name).read_bytes()
        total += len(data)
        if total > 20_000_000:
            raise ToolError("Snapshot excede 20 MB")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return workspace.digest()
