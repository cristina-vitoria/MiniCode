"""Ferramentas públicas e runner com snapshot, launcher isolado e relatório próprio."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid

from .workspace import Workspace, ToolError, copy_filtered, RESERVED_MODULES

MAX_OUTPUT = 1_000_000


class TestRunner:
    def __init__(self, root, mode="docker", timeout=30, profile="unittest", python=None,
                 image="minicode-tests:parte1", acceptance_dir=None):
        if mode not in {"docker", "local"} or profile not in {"pytest", "unittest"} or timeout < 1:
            raise ValueError("Runner, perfil ou timeout inválido")
        self.root = Path(root).resolve()
        self.mode, self.timeout, self.profile = mode, timeout, profile
        self.python = str(Path(python).absolute()) if python else sys.executable
        self.image = image
        self.acceptance_dir = Path(acceptance_dir).resolve() if acceptance_dir else None
        if self.acceptance_dir and (not self.acceptance_dir.is_dir() or self.acceptance_dir.is_relative_to(self.root)
                                    or self.root.is_relative_to(self.acceptance_dir)):
            raise ValueError("Aceitação deve ser um diretório confiável fora do projeto")
        self.workspace = Workspace(root)

    @property
    def description(self):
        return f"{self.profile} pelo launcher confiável; sem comandos arbitrários"

    def run(self):
        result = self.run_suite()
        if result["passed"] and self.acceptance_dir:
            acceptance = self.run_suite(self.acceptance_dir)
            result["acceptance"] = acceptance
            result["passed"] = acceptance["passed"] and result["source_digest"] == acceptance["source_digest"]
            result["verified"] = result["verified"] and acceptance["verified"]
        return result

    def run_suite(self, trusted_tests=None):
        started = time.monotonic()
        result = {"passed": False, "verified": False, "tests": 0, "discovered": 0,
                  "returncode": None, "timed_out": False, "output": "", "source_digest": None}
        try:
            self.workspace.verify_protected()
            digest = self.workspace.digest()
            # Recusa sombreamento mesmo quando o arquivo já existia antes do agente.
            for path in self.root.iterdir():
                if path.name.removesuffix(".py") in RESERVED_MODULES:
                    raise ToolError(f"Nome reservado no projeto: {path.name}")
            with tempfile.TemporaryDirectory(prefix="minicode-run-") as temporary:
                base = Path(temporary)
                project = base / "project"
                copy_filtered(self.root, project)
                if Workspace(project).digest() != digest:
                    raise ToolError("Projeto mudou durante a cópia")
                trusted = base / "trusted"
                trusted.mkdir()
                for name in ("_test_worker.py", "runner.ini"):
                    (trusted / name).write_bytes(Path(__file__).with_name(name).read_bytes())
                if trusted_tests:
                    # Os testes e conftest do candidato não entram na aceitação independente.
                    import shutil
                    shutil.rmtree(project / "tests", ignore_errors=True)
                    copy_filtered(trusted_tests, trusted / "acceptance")
                out = base / "result"
                out.mkdir()
                snapshot_digest = Workspace(project).digest()
                name = "minicode-" + uuid.uuid4().hex
                if self.mode == "docker":
                    command = ["docker", "run", "--rm", "--name", name, "--network=none", "--read-only",
                               "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=64",
                               "--memory=256m", "--cpus=1", "--user", f"{os.getuid()}:{os.getgid()}",
                               "--tmpfs", "/tmp:rw,nosuid,size=32m", "-e", "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
                               "-v", f"{project}:/workspace:ro", "-v", f"{trusted}:/trusted:ro",
                               "-v", f"{out}:/result:rw", "-w", "/workspace", self.image,
                               "python", "-I", "-B", "/trusted/_test_worker.py", "/workspace", self.profile,
                               "/result/report.json", "/trusted/acceptance" if trusted_tests else ""]
                else:
                    command = [self.python, "-I", "-B", str(trusted / "_test_worker.py"), str(project),
                               self.profile, str(out / "report.json"), str(trusted / "acceptance") if trusted_tests else ""]
                result.update(self._execute(command, base, name))
                report_path = out / "report.json"
                report = None
                if report_path.is_file() and not report_path.is_symlink() and report_path.stat().st_size < 10000:
                    try:
                        report = json.loads(report_path.read_text(encoding="utf-8"))
                    except (ValueError, OSError):
                        pass
                valid = (isinstance(report, dict) and report.get("protocol") == 1
                         and report.get("completed") is True and type(report.get("passed")) is bool
                         and all(type(report.get(key)) is int and report[key] >= 0
                                 for key in ("tests", "discovered", "failed", "skipped"))
                         and report["tests"] <= report["discovered"])
                self.workspace.verify_protected()
                unchanged = self.workspace.digest() == digest and Workspace(project).digest() == snapshot_digest
                if valid:
                    result.update(tests=report["tests"], discovered=report["discovered"], skipped=report["skipped"])
                result.update(source_digest=digest, verified=bool(valid and unchanged and not result["timed_out"]),
                              passed=bool(valid and unchanged and not result["timed_out"]
                                          and result["returncode"] == 0 and report["passed"]
                                          and report["tests"] > 0 and report["failed"] == 0
                                          and (not trusted_tests or report["skipped"] == 0)))
                if not valid:
                    result["error"] = "Relatório de testes ausente, incompleto ou inválido"
                if not unchanged:
                    result["error"] = "Projeto alterado durante a verificação"
        except (OSError, ToolError, ValueError) as exc:
            result.update(passed=False, verified=False, error=str(exc))
        result["seconds"] = time.monotonic() - started
        return result

    def _execute(self, command, base, container_name):
        env = {k: v for k, v in os.environ.items() if k in {"PATH", "SYSTEMROOT", "DOCKER_HOST", "XDG_RUNTIME_DIR"}}
        env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", HOME=str(base))
        process = None
        interrupted = True
        timed_out = False
        started = time.monotonic()
        try:
            with tempfile.TemporaryFile() as output:
                process = subprocess.Popen(command, cwd=base, env=env, stdout=output,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                while process.poll() is None:
                    if time.monotonic() - started > self.timeout or os.fstat(output.fileno()).st_size > MAX_OUTPUT:
                        timed_out = True
                        self._kill(process)
                        break
                    time.sleep(0.02)
                process.wait()
                output.seek(0)
                data = output.read(MAX_OUTPUT + 1)
                if len(data) > MAX_OUTPUT:
                    timed_out = True
                interrupted = False
                # Saída completa até o orçamento; contagem não depende do texto.
                return {"returncode": process.returncode, "timed_out": timed_out,
                        "output": data[:MAX_OUTPUT].decode("utf-8", errors="replace"), "command": command}
        finally:
            if process is not None:
                # Mata também descendentes que tenham sobrevivido ao processo principal.
                self._kill(process)
            if self.mode == "docker" and (timed_out or interrupted):
                try:
                    subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=10, check=False)
                except (OSError, subprocess.TimeoutExpired):
                    pass

    @staticmethod
    def _kill(process):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
