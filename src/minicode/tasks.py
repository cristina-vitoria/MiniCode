"""Catálogo das seis tarefas de softwareteste e aceitação independente."""
import ast
from dataclasses import dataclass
from pathlib import Path
import re
import tempfile

from .tools import TestRunner
from .workspace import Workspace, copy_filtered

VERSION = 'softwareteste-v4.1'


@dataclass(frozen=True)
class Task:
    id: str
    kind: str
    test_file: str
    editable: tuple[str, ...]
    guidance: tuple[str, ...] = ()
    required: tuple[str, ...] = ()


TASKS = (
    Task('discount','implementacao_funcao','test_cart_service.py',('app/cart_service.py',),(
        'Exatamente int exclui bool e float: valide com type(valor) is int e não afrouxe esse contrato.',
        'Testes de truncamento usam operandos inteiros; float deve gerar ValueError.',),
        ('app/cart_service.py',)),
    Task('tax','correcao_bug','test_tax_service.py',('app/tax_service.py',),(
        'Preserve literalmente as validações e mude somente a escala do cálculo defeituoso.',
        'Exceções devem ser testadas com pytest.raises, não comparadas como valores de retorno.',),
        ('app/tax_service.py',)),
    Task('pagination','modificacao_api','test_pagination.py',('app/controllers.py','app/routes.py','app/repositories.py'),(
        'Conversão type=int em request.args.get silencia entradas inválidas; leia strings cruas.',
        'str.isdigit aceita algarismos Unicode; exija isascii e isdigit antes de converter.',),
        ('app/controllers.py',)),
    Task('tests','criacao_testes','test_services.py',(),(
        'Os testes devem passar primeiro na implementação original; falhar nos mutantes é desejável.',
        'Aplique strip e upper antes de contar: o limite inválido superior começa em 13 caracteres.',),()),
    Task('users','validacao_dados','test_user_validation.py',('app/controllers.py','app/user_service.py'),(
        'O service valida tipos antes de chamar strip, levanta ValueError e retorna somente o usuário.',
        'O controller captura ValueError e o traduz para HTTP 400; não retorne tuplas HTTP no service.',),
        ('app/controllers.py','app/user_service.py')),
    Task('refactor','refatoracao','test_report_refactor.py',('app/report_service.py',),(
        'A função auxiliar calcula valores de um pedido; o laço externo deve acumulá-los, não sobrescrever totais.',
        'A auxiliar é função de módulo, não atributo de build_sales_report; teste-a ou observe-a pelo módulo.',),
        ('app/report_service.py',)),
)


def prompts(source):
    blocks = re.findall(r'```text\s*\n(.*?)```', (Path(source)/'TASKS.md').read_text(encoding='utf-8'), re.S)
    if len(blocks) != len(TASKS):
        raise ValueError('TASKS.md deve conter os seis prompts em blocos text')
    return {task.id: block + '\n\nOrientações operacionais derivadas do contrato:\n'
            + '\n'.join('- ' + item for item in task.guidance)
            for task, block in zip(TASKS, blocks)}


def contract_issues(task_id, project):
    """Pré-verificação transparente de restrições literais dos seis enunciados."""
    project = Path(project)
    issues = []

    def read(name):
        return (project / name).read_text(encoding='utf-8')

    test_file = next(task.test_file for task in TASKS if task.id == task_id)
    test_source = read('tests/' + test_file)
    if task_id in {'discount', 'tax'}:
        if 'raises(TypeError)' in test_source or '== ValueError' in test_source:
            issues.append('O contrato exige ValueError; use raises(ValueError), nunca TypeError ou comparação com a classe.')
    elif task_id == 'pagination':
        source = read('app/controllers.py')
        compact = ''.join(source.split())
        if 'type=int' in compact:
            issues.append('request.args.get(type=int) converte falhas em default; leia os parâmetros como strings cruas.')
        if '.isascii()' not in source or '.isdigit()' not in source:
            issues.append('Valide cada parâmetro com isascii() e isdigit() antes de int().')
        if 'max(int(' in compact or 'min(max(' in compact:
            issues.append('Valores fora da faixa devem gerar HTTP 400; não os limite silenciosamente com min/max.')
    elif task_id == 'tests':
        try:
            tree = ast.parse(test_source)
        except SyntaxError:
            return issues
        for node in ast.walk(tree):
            if not isinstance(node, ast.With):
                continue
            context = ast.dump(node.items[0].context_expr, include_attributes=False)
            if 'raises' not in context and 'assertRaises' not in context:
                continue
            for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
                if not (isinstance(call.func, ast.Name) and call.func.id == 'normalize_coupon'
                        and call.args and isinstance(call.args[0], ast.Constant)
                        and isinstance(call.args[0].value, str)):
                    continue
                value = call.args[0].value.strip().upper()
                if 3 <= len(value) <= 12 and value.isascii() and value.isalnum():
                    issues.append(
                        f'{call.args[0].value!r} é cupom válido depois de strip/upper; '
                        'não espere ValueError para espaços somente nas extremidades.')
    elif task_id == 'users':
        service = read('app/user_service.py')
        controller = read('app/controllers.py')
        compact = ''.join(service.split())
        if 'raiseValueError' not in compact or "return{'error'" in compact:
            issues.append('O service deve levantar ValueError e nunca retornar resposta ou tupla HTTP.')
        if 'exceptValueError' not in ''.join(controller.split()):
            issues.append('O controller deve capturar ValueError e convertê-lo em HTTP 400.')
        exact_age_type = 'type(age)isint' in compact or 'type(age)isnotint' in compact
        if 'isinstance(age,int)' in compact or not exact_age_type:
            issues.append('age exige type(age) is int para rejeitar bool.')
        if '.isspace()' not in service:
            issues.append('O e-mail normalizado deve rejeitar qualquer whitespace interno com isspace().')
        if not re.search(r'email\s*=.*\.strip\s*\(', service):
            issues.append('Atribua email normalizado com strip antes de validar e armazenar.')
    elif task_id == 'refactor':
        source = read('app/report_service.py')
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return issues
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        helpers = set(functions) - {'build_sales_report'}
        if not helpers:
            issues.append('Extraia pelo menos uma função auxiliar de módulo; helper aninhada não atende ao contrato.')
        else:
            build = functions.get('build_sales_report')
            called = {node.func.id for node in ast.walk(build) if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Name)} if build else set()
            if not helpers & called:
                issues.append('build_sales_report deve chamar a função auxiliar de módulo pelo mesmo nome definido.')
    return issues


class TaskAcceptance:
    def __init__(self, task, baseline, mode='docker', timeout=30, python=None, image='minicode-tests:parte1'):
        self.task = task
        self.baseline = Path(baseline)
        self.initial = Workspace(baseline).manifest()
        self.options = dict(mode=mode, timeout=timeout, profile='pytest', python=python, image=image)

    def __call__(self, project):
        project = Path(project)
        current = Workspace(project).manifest()
        changed = {name for name in self.initial.keys() | current.keys() if self.initial.get(name) != current.get(name)}
        forbidden = [name for name in changed if name in self.initial and name not in self.task.editable and not name.endswith('.md')]
        # Testes originais, fixtures e demais pendências não podem mudar.
        new_test = 'tests/' + self.task.test_file
        if forbidden or new_test not in current or new_test in self.initial:
            return {'passed':False,'verified':True,'tests':0,'output':f'Escopo inválido ou teste obrigatório ausente: {forbidden or new_test}'}
        if self.task.id == 'tests':
            if any(name.startswith('app/') for name in changed):
                return {'passed':False,'verified':True,'tests':0,'output':'A tarefa de testes deve preservar toda a aplicação'}
            return self._mutations(project)
        with tempfile.TemporaryDirectory(prefix='minicode-acceptance-') as tmp:
            suite = Path(tmp)/'tests'
            suite.mkdir()
            oracle = Path(__file__).with_name('acceptance')/(self.task.id+'.py')
            (suite/'test_acceptance.py').write_bytes(oracle.read_bytes())
            return TestRunner(project, **self.options).run_suite(suite)

    def _mutations(self, project):
        source = (self.baseline/'app/services.py').read_text(encoding='utf-8')
        mutants = [source.replace('>= 20000','> 20000'), source.replace('// 1000','// 100'),
                   source.replace('code.strip().upper()','code.upper()'), source.replace('code.strip().upper()','code.strip()')]
        trials = []
        for index, code in enumerate([source, *mutants]):
            with tempfile.TemporaryDirectory(prefix='minicode-mutation-') as tmp:
                root = Path(tmp)/'project'
                copy_filtered(self.baseline, root)
                (root/'tests'/self.task.test_file).write_bytes((project/'tests'/self.task.test_file).read_bytes())
                (root/'app/services.py').write_text(code,encoding='utf-8')
                # Executa somente o teste novo. Os testes-base não podem matar mutantes por ele.
                suite = Path(tmp)/'suite'
                suite.mkdir()
                (suite/self.task.test_file).write_bytes((project/'tests'/self.task.test_file).read_bytes())
                trials.append(TestRunner(root, **self.options).run_suite(suite))
        killed = sum(trial['verified'] and trial['tests'] > 0 and trial['returncode'] == 1 and not trial['passed'] for trial in trials[1:])
        passed = trials[0]['passed'] and killed == 4
        return {'passed':passed,'verified':all(t['verified'] for t in trials),'tests':trials[0]['tests'],
                'original_passed':trials[0]['passed'],'killed':killed,'total':4,'trials':trials,
                'output':(f'Testes no original: {trials[0]["passed"]}; mutantes detectados: {killed}/4. '
                          'O original deve passar; falhas nos mutantes significam detecção correta.\n'
                          + trials[0]['output'])}
