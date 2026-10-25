"""Catálogo das seis tarefas de softwareteste e aceitação independente."""
from dataclasses import dataclass
from pathlib import Path
import re
import tempfile

from .tools import TestRunner
from .workspace import Workspace, copy_filtered

VERSION = 'softwareteste-v1'


@dataclass(frozen=True)
class Task:
    id: str
    kind: str
    test_file: str
    editable: tuple[str, ...]


TASKS = (
    Task('discount','implementacao_funcao','test_cart_service.py',('app/cart_service.py',)),
    Task('tax','correcao_bug','test_tax_service.py',('app/tax_service.py',)),
    Task('pagination','modificacao_api','test_pagination.py',('app/controllers.py','app/routes.py','app/repositories.py')),
    Task('tests','criacao_testes','test_services.py',()),
    Task('users','validacao_dados','test_user_validation.py',('app/controllers.py','app/user_service.py')),
    Task('refactor','refatoracao','test_report_refactor.py',('app/report_service.py',)),
)


def prompts(source):
    blocks = re.findall(r'```text\s*\n(.*?)```', (Path(source)/'TASKS.md').read_text(encoding='utf-8'), re.S)
    if len(blocks) != len(TASKS):
        raise ValueError('TASKS.md deve conter os seis prompts em blocos text')
    return dict(zip((task.id for task in TASKS), blocks))


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
                'killed':killed,'total':4,'trials':trials,
                'output':f'Testes no original: {trials[0]["passed"]}; mutantes detectados: {killed}/4\n' + '\n'.join(t['output'] for t in trials)}
