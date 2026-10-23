"""Ferramentas restritas e execução de testes com comando fixo."""
import hashlib
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import uuid


class ToolError(ValueError):
    pass


class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ToolError("Projeto deve ser diretório")
        self.original_tests = {p for p in self.list_files() if self.is_test(p)}
        self.revision = 0
        self.changed = set()

    @staticmethod
    def is_test(name):
        p = Path(name)
        return "tests" in p.parts or p.name.startswith("test_") or p.name.endswith("_test.py")

    def path(self, name, write=False):
        p = Path(name)
        if not name or p.is_absolute() or ".." in p.parts:
            raise ToolError("Caminho deve ser relativo e interno ao projeto")
        if any(part.startswith(".") or part in {"__pycache__", "node_modules", "venv"} for part in p.parts):
            raise ToolError("Diretório oculto ou reservado")
        if p.suffix in {".pem", ".key"} or p.name.lower() in {"credentials", "secrets.json"}:
            raise ToolError("Arquivo sensível")
        current = self.root
        for part in p.parts:
            current = current / part
            if current.is_symlink():
                raise ToolError("Links simbólicos não são permitidos")
        resolved = current.resolve()
        if not resolved.is_relative_to(self.root):
            raise ToolError("Caminho fora do projeto")
        if current.exists() and current.is_file() and current.stat().st_nlink > 1:
            raise ToolError("Hard links não são permitidos")
        if write and name in self.original_tests:
            raise ToolError("Testes preexistentes são protegidos contra alteração")
        return current

    def list_files(self):
        result = []
        for folder, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in {"__pycache__", "node_modules", "venv"} and not (Path(folder) / d).is_symlink())
            for filename in sorted(files):
                name = (Path(folder) / filename).relative_to(self.root).as_posix()
                try:
                    self.path(name)
                    result.append(name)
                except ToolError:
                    continue
                if len(result) >= 1000:
                    return result
        return result

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
        self.revision += 1
        self.changed.add(path)
        return {"path": path, "revision": self.revision, "sha256": hashlib.sha256(content.encode()).hexdigest()}

    def search_code(self, query):
        if not isinstance(query, str) or not query:
            raise ToolError("Busca vazia")
        results = []
        for name in self.list_files():
            try:
                for n, line in enumerate(self.read_file(name).splitlines(), 1):
                    if query in line:
                        results.append({"path": name, "line": n, "text": line[:300]})
                    if len(results) >= 50:
                        return results
            except (UnicodeError, OSError, ToolError):
                continue
        return results


class TestRunner:
    def __init__(self, root, mode="docker", timeout=30):
        if mode not in {"docker", "local"} or timeout < 1:
            raise ValueError("Runner ou timeout inválido")
        self.root, self.mode, self.timeout = Path(root).resolve(), mode, timeout

    def run(self):
        test_args = ["-m", "unittest", "discover", "-s", "tests", "-v"]
        name = "minicode-" + uuid.uuid4().hex
        if self.mode == "docker":
            command = ["docker", "run", "--rm", "--name", name, "--network=none",
                       "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                       "--pids-limit=64", "--memory=256m", "--cpus=1",
                       "--user", f"{os.getuid()}:{os.getgid()}", "--tmpfs", "/tmp:rw,nosuid,size=32m",
                       "-e", "PYTHONDONTWRITEBYTECODE=1", "-v", f"{self.root}:/workspace:ro",
                       "-w", "/workspace", "python:3.12-slim", "python", *test_args]
        else:
            command = [sys.executable, "-B", *test_args]
        env = {k: v for k, v in os.environ.items() if k in {"PATH", "SYSTEMROOT", "DOCKER_HOST", "XDG_RUNTIME_DIR"}}
        env.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
        start = time.monotonic()
        timed_out = False
        try:
            with tempfile.TemporaryFile() as output:
                proc = subprocess.Popen(command, cwd=self.root, env=env, stdout=output,
                                        stderr=subprocess.STDOUT, start_new_session=True)
                while proc.poll() is None:
                    if time.monotonic() - start > self.timeout or output.tell() > 1_000_000:
                        timed_out = True
                        os.killpg(proc.pid, signal.SIGKILL)
                        break
                    time.sleep(0.02)
                proc.wait()
                output.seek(0)
                log = output.read(16_000).decode("utf-8", errors="replace")
            counts = re.findall(r"Ran (\d+) tests? in", log)
            count = int(counts[-1]) if counts else 0
            skipped = re.findall(r"skipped=(\d+)", log)
            executed = count - (int(skipped[-1]) if skipped else 0)
            return {"passed": proc.returncode == 0 and executed > 0 and not timed_out,
                    "returncode": proc.returncode, "tests": executed, "discovered": count, "output": log,
                    "timed_out": timed_out, "command": command, "seconds": time.monotonic() - start}
        except OSError:
            return {"passed": False, "tests": 0, "output": "Runner indisponível; confira Docker ou Python", "command": command}
        finally:
            if self.mode == "docker" and timed_out:
                subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=10, check=False)
