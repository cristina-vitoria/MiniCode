"""Política única de caminhos, integridade dos testes e snapshots filtrados."""
import ast
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
    def __init__(self, root, editable_paths=None):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ToolError("Projeto deve ser diretório")
        self.revision = 0
        self.changed = set()
        self.editable_paths = None if editable_paths is None else {
            Path(name).as_posix() for name in editable_paths
        }
        self.original_files = set(self.files())
        self.original_python_bindings = {
            name: self._python_bindings(self.read_file(name))
            for name in self.original_files if name.endswith(".py")
        }
        self.original_import_cycles = self._import_cycles()
        # Sem o limite de apresentação de list_files: todos os testes são protegidos.
        self.original_tests = {name for name in self.files() if self.is_test(name)}
        self.protected = {name: self.hash_file(name) for name in self.files()
                          if self.is_test(name) or Path(name).name in CONTROL_FILES}
        self.frozen_generated_tests = set()
        self.frozen_production = set()

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
            if self.editable_paths is not None and canonical not in self.editable_paths:
                raise ToolError(f"Arquivo fora do escopo de escrita: {canonical}")
            if canonical in self.frozen_production:
                raise ToolError(
                    f"Produção aprovada e congelada: {canonical}; corrija somente o teste novo que falha")
            if canonical in self.frozen_generated_tests:
                raise ToolError(
                    f"Teste congelado após reprovação independente: {canonical}; corrija o código de produção")
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

    def protect_current_tests(self):
        """Congela testes presentes sem impedir a criação de novos arquivos de teste."""
        added = []
        for name in self.files():
            if self.is_test(name) and name not in self.protected:
                self.protected[name] = self.hash_file(name)
                self.frozen_generated_tests.add(name)
                added.append(name)
        return sorted(added)

    def unprotect_generated_tests(self):
        """Libera somente testes criados nesta execução; testes originais continuam imutáveis."""
        thawed = []
        for name in sorted(self.frozen_generated_tests):
            if name not in self.original_tests:
                self.protected.pop(name, None)
                thawed.append(name)
        self.frozen_generated_tests.clear()
        return thawed

    def protect_changed_production(self):
        """Congela produção aceita pelo oráculo para impedir regressão em reparos de testes."""
        added = []
        for name in sorted(self.changed):
            if not self.is_test(name) and name not in self.protected:
                self.protected[name] = self.hash_file(name)
                self.frozen_production.add(name)
                added.append(name)
        return added

    def read_file(self, path):
        p = self.path(path)
        if p.stat().st_size > 40_000:
            raise ToolError("Arquivo excede 40 KB; divida-o antes de usar MiniCode")
        return p.read_text(encoding="utf-8")

    def write_file(self, path, content):
        if not isinstance(content, str) or len(content.encode()) > 40_000:
            raise ToolError("Conteúdo inválido ou maior que 40 KB")
        p = self.path(path, write=True)
        canonical = p.resolve().relative_to(self.root).as_posix()
        normalized_escaped_newlines = False
        if p.suffix == ".py":
            try:
                compile(content, p.as_posix(), "exec")
            except SyntaxError as exc:
                repaired = content.replace("\\n", "\n")
                if repaired != content:
                    try:
                        compile(repaired, p.as_posix(), "exec")
                    except SyntaxError:
                        pass
                    else:
                        content = repaired
                        normalized_escaped_newlines = True
                if not normalized_escaped_newlines:
                    location = f"linha {exc.lineno}" if exc.lineno else "local desconhecido"
                    raise ToolError(f"Python inválido em {location}: {exc.msg}") from None
            if canonical in self.original_python_bindings:
                missing = self.original_python_bindings[canonical] - self._python_bindings(content)
                if missing:
                    raise ToolError("Reescrita remove ou altera APIs/imports preexistentes: "
                                    + ", ".join(sorted(missing)))
            cycles = self._import_cycles({canonical: content}) - self.original_import_cycles
            if cycles:
                cycle = " -> ".join(next(iter(sorted(cycles))))
                raise ToolError(f"Import circular novo: {cycle}")
        if p.is_file() and p.read_text(encoding="utf-8") == content:
            raise ToolError("Escrita sem alteração: releia o arquivo e proponha conteúdo diferente")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        name = p.resolve().relative_to(self.root).as_posix()
        self.revision += 1
        self.changed.add(name)
        return {"path": name, "revision": self.revision, "sha256": self.hash_file(name),
                "normalized_escaped_newlines": normalized_escaped_newlines}

    def replace_python_function(self, path, name, content):
        """Substitui uma função e pode inserir novas auxiliares de módulo no mesmo bloco."""
        if not isinstance(name, str) or not name.isidentifier() or not isinstance(content, str):
            raise ToolError("Nome ou conteúdo de função inválido")
        if len(content.encode()) > 20_000:
            raise ToolError("Função excede 20 KB")
        source = self.read_file(path)
        normalized_escaped_newlines = False
        try:
            tree = ast.parse(source)
            replacement = ast.parse(content)
        except SyntaxError as exc:
            repaired = content.replace("\\n", "\n")
            if repaired != content:
                try:
                    replacement = ast.parse(repaired)
                    tree = ast.parse(source)
                except SyntaxError:
                    pass
                else:
                    content = repaired
                    normalized_escaped_newlines = True
            if not normalized_escaped_newlines:
                raise ToolError(f"Python inválido na substituição: {exc.msg}") from None
        candidates = [node for node in tree.body
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
        replacement_nodes = [node for node in replacement.body
                             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        target_replacements = [node for node in replacement_nodes if node.name == name]
        if (len(candidates) != 1 or len(target_replacements) != 1
                or len(replacement.body) != len(replacement_nodes)):
            raise ToolError("replace_python_function exige a função alvo e somente funções auxiliares novas")
        target = candidates[0]
        if type(target_replacements[0]) is not type(target):
            raise ToolError("A função substituta deve preservar nome e tipo síncrono/assíncrono")
        replacement_names = [node.name for node in replacement_nodes]
        if len(replacement_names) != len(set(replacement_names)):
            raise ToolError("Funções duplicadas no bloco substituto")
        existing_names = {node.name for node in tree.body
                          if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name != name}
        duplicate_helpers = existing_names & (set(replacement_names) - {name})
        if duplicate_helpers:
            raise ToolError("Auxiliar já existe no módulo: " + ", ".join(sorted(duplicate_helpers)))
        start = min([target.lineno] + [item.lineno for item in target.decorator_list]) - 1
        lines = source.splitlines(keepends=True)
        suffix = "" if content.endswith("\n") else "\n"
        updated = "".join(lines[:start]) + content + suffix + "".join(lines[target.end_lineno:])
        result = self.write_file(path, updated)
        result["normalized_escaped_newlines"] = normalized_escaped_newlines
        return result

    @staticmethod
    def _python_bindings(content):
        """Nomes públicos estruturais que uma edição de arquivo original deve preservar."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return set()
        names = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add("definition:" + node.name)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    returns = (ast.dump(node.returns, include_attributes=False)
                               if node.returns is not None else "None")
                    signature = ast.dump(node.args, include_attributes=False) + ":" + returns
                    names.add("signature:" + node.name + ":" + signature)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    names.add("import:" + (alias.asname or alias.name.split(".")[0]))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    names.add("import:" + (alias.asname or alias.name))
        return names

    def _import_cycles(self, overrides=None):
        """Retorna ciclos entre módulos Python locais, ignorando dependências externas."""
        overrides = overrides or {}
        names = set(self.original_files) | set(overrides)
        modules = {}
        for name in names:
            if not name.endswith(".py"):
                continue
            path = Path(name)
            parts = list(path.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            if parts:
                modules[".".join(parts)] = name
        graph = {module: set() for module in modules}
        for module, name in modules.items():
            try:
                content = overrides.get(name, self.read_file(name))
                tree = ast.parse(content)
            except (OSError, UnicodeError, SyntaxError, ToolError):
                continue
            package = module if Path(name).stem == "__init__" else module.rpartition(".")[0]
            for node in ast.walk(tree):
                target = None
                if isinstance(node, ast.ImportFrom):
                    if node.level:
                        package_parts = package.split(".") if package else []
                        keep = max(0, len(package_parts) - node.level + 1)
                        base = ".".join(package_parts[:keep])
                        target = ".".join(part for part in (base, node.module or "") if part)
                    else:
                        target = node.module
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in modules:
                            graph[module].add(alias.name)
                if target in modules:
                    graph[module].add(target)
        cycles = set()

        def visit(node, path):
            if node in path:
                ring = path[path.index(node):] + [node]
                core = ring[:-1]
                rotations = [tuple(core[i:] + core[:i] + [core[i]]) for i in range(len(core))]
                cycles.add(min(rotations))
                return
            for target in graph.get(node, ()):
                visit(target, path + [node])

        for module in graph:
            visit(module, [])
        return cycles

    def replace_text(self, path, old, new):
        if not isinstance(old, str) or not isinstance(new, str) or not old:
            raise ToolError("old deve ser texto não vazio e new deve ser texto")
        if len(old.encode()) > 20_000 or len(new.encode()) > 20_000:
            raise ToolError("Substituição excede 20 KB")
        content = self.read_file(path)
        occurrences = content.count(old)
        if occurrences != 1:
            hint = ("releia o arquivo" if occurrences == 0 else
                    "use um trecho maior e único ou replace_python_function")
            raise ToolError(f"replace_text exige uma ocorrência exata; encontradas: {occurrences}; {hint}")
        return self.write_file(path, content.replace(old, new, 1))

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
