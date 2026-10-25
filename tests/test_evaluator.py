import json
import os
from pathlib import Path
import tempfile
import unittest
import sys

from minicode.evaluator import evaluate, metrics
from minicode.tasks import TASKS, TaskAcceptance
from minicode.llm import ModelError
from minicode.workspace import copy_filtered

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'softwareteste'
PYTHON = os.environ.get('MINICODE_TEST_PYTHON', str(SOURCE/'.venv/bin/python')
                        if (SOURCE/'.venv/bin/python').exists() else sys.executable)
FIXTURES = Path(__file__).with_name('fixtures')


def modifications(task):
    changes = {}
    if task.id == 'discount':
        changes['app/cart_service.py'] = (FIXTURES/'discount.py').read_text()
    elif task.id == 'tax':
        changes['app/tax_service.py'] = (SOURCE/'app/tax_service.py').read_text().replace('// 1000','// 100')
    elif task.id == 'pagination':
        source = (SOURCE/'app/controllers.py').read_text()
        begin, end = source.index('def list_products():'), source.index('def create_user():')
        changes['app/controllers.py'] = source[:begin]+'''def list_products():
    def parameter(name, default):
        value = request.args.get(name, default)
        if not value.isascii() or not value.isdigit() or int(value) < 1:
            raise ValueError(name)
        return int(value)
    try:
        page, size = parameter('page', '1'), parameter('page_size', '20')
        if size > 100: raise ValueError('size')
    except ValueError:
        return jsonify(error='invalid pagination'), 400
    items = current_app.extensions['store'].list_products()
    total = len(items)
    return jsonify(items=items[(page-1)*size:page*size], total=total, page=page, page_size=size, total_pages=(total+size-1)//size)


'''+source[end:]
    elif task.id == 'users':
        changes['app/user_service.py'] = (FIXTURES/'user_service.py').read_text()
        changes['app/controllers.py'] = (SOURCE/'app/controllers.py').read_text().replace(
            '    user = register_user(current_app.extensions["store"], payload)',
            '    try:\n        user = register_user(current_app.extensions["store"], payload)\n    except ValueError as exc:\n        return jsonify(error=str(exc)), 400')
    elif task.id == 'refactor':
        changes['app/report_service.py'] = (FIXTURES/'report_service.py').read_text()
    if task.id == 'tests':
        test_source = (FIXTURES/'services_tests.py').read_text()
    else:
        # Soluções roteirizadas testam o harness, não a capacidade de uma LLM.
        test_source = (ROOT/'src/minicode/acceptance'/(task.id+'.py')).read_text()
    changes['tests/'+task.test_file] = test_source
    return changes


class Client:
    def __init__(self,task,correct=True):
        responses = [{'objective':task.id,'acceptance_criteria':['Atender o contrato']},
                     {'steps':['Implementar','Testar'],'test_strategy':'pytest'}]
        if correct:
            responses += [{'tool':'write_file','args':{'path':name,'content':content}}
                          for name,content in modifications(task).items()]
        responses.append({'tool':'run_tests','args':{}})
        self.responses = iter(responses)

    def complete(self,messages):
        return json.dumps(next(self.responses))


class EvaluationTests(unittest.TestCase):
    def test_metrics_include_failures(self):
        rows = [{'success':True,'iterations':1,'llm_calls':4},
                {'success':True,'iterations':2,'llm_calls':8},
                {'success':False,'iterations':3,'llm_calls':9}]
        result=metrics(rows)
        self.assertAlmostEqual(result['TaskSuccessRate'],2/3)
        self.assertAlmostEqual(result['FirstAttemptSuccess'],1/3)
        self.assertEqual(result['AverageIterations'],2)
        self.assertEqual(result['AverageLLMCalls'],7)
        self.assertEqual(metrics([])['total_tasks'],0)

    def test_six_categories(self):
        self.assertEqual(len({task.kind for task in TASKS}),6)

    def test_all_correct_solutions_pass_independent_acceptance(self):
        tasks=iter(TASKS)
        with tempfile.TemporaryDirectory() as tmp:
            result=evaluate(lambda:Client(next(tasks)),Path(tmp)/'results','local',source=SOURCE,python=PYTHON,max_iterations=1)
            self.assertTrue(result['complete'])
            self.assertEqual(result['metrics']['TaskSuccessRate'],1,result['tasks'])
            self.assertEqual(result['metrics']['FirstAttemptSuccess'],1)
            for row in result['tasks']:
                self.assertTrue(Path(row['trace']).is_dir())
                self.assertTrue(row['acceptance']['verified'])

    def test_client_failure_keeps_six_in_denominator(self):
        tasks=iter(TASKS)
        def factory():
            task=next(tasks)
            if task.id == 'discount': raise ModelError('offline')
            return Client(task,correct=False)
        with tempfile.TemporaryDirectory() as tmp:
            result=evaluate(factory,Path(tmp)/'results','local',source=SOURCE,python=PYTHON,max_iterations=1)
        self.assertTrue(result['complete'])
        self.assertEqual(result['metrics']['total_tasks'],6)
        self.assertEqual(result['metrics']['TaskSuccessRate'],0)
        self.assertEqual(result['tasks'][0]['llm_calls'],0)
        self.assertEqual(result['tasks'][-1]['state'],'FAILED')

    def test_interrupt_preserves_full_denominator_and_pending_tasks(self):
        def factory(): raise KeyboardInterrupt()
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'results'
            with self.assertRaises(KeyboardInterrupt):
                evaluate(factory,output,'local',source=SOURCE,python=PYTHON)
            result=json.loads((output/'results.json').read_text())
        self.assertEqual(result['metrics']['total_tasks'],6)
        self.assertFalse(result['complete'])
        self.assertEqual(result['tasks'][0]['state'],'FAILED')

    def test_weak_tests_cannot_pass_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'project'
            copy_filtered(SOURCE,root)
            (root/'tests/test_services.py').write_text('def test_trivial(): assert True\n')
            result=TaskAcceptance(TASKS[3],SOURCE,'local',python=PYTHON)(root)
        self.assertFalse(result['passed'])
        self.assertEqual(result['killed'],0)

    def test_preserves_source_and_rejects_out_of_scope_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'project';copy_filtered(SOURCE,root)
            (root/'tests/test_services.py').write_text((FIXTURES/'services_tests.py').read_text())
            (root/'app/services.py').write_text('modified\n')
            result=TaskAcceptance(TASKS[3],SOURCE,'local',python=PYTHON)(root)
        self.assertFalse(result['passed'])
