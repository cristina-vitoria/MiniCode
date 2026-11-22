import json
from pathlib import Path
import tempfile
import unittest

from minicode.agent import Agent, State
from minicode.llm import TransientModelError, parse_object
from minicode.tools import TestRunner, ToolError


class ScriptClient:
    def __init__(self, values):
        self.values = iter(values)
    def complete(self, messages):
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, str) else json.dumps(value)


class InspectingClient(ScriptClient):
    def __init__(self, values):
        super().__init__(values)
        self.messages = []
    def complete(self, messages):
        self.messages.append(messages)
        return super().complete(messages)


SPEC = {"objective": "Objetivo", "acceptance_criteria": ["Retorna 1"]}
PLAN = {"steps": ["Implementar", "Testar"], "test_strategy": "unittest"}


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def agent(self, client=None, **kwargs):
        # Verificador simulado para os testes unitários da máquina de estados.
        kwargs.setdefault('acceptance', lambda root: {'passed':True,'verified':True,'tests':1,'output':'fixture'})
        return Agent(self.root, client or ScriptClient([]), TestRunner(self.root, "local", 3), **kwargs)

    def test_demo_repairs_real_failed_tests(self):
        (self.root / "tests").mkdir()
        (self.root / "solution.py").write_text("def factorial(n): raise NotImplementedError\n")
        (self.root / "tests/test_factorial.py").write_text("import unittest\nfrom solution import factorial\nclass T(unittest.TestCase):\n    def test_values(self):\n        self.assertEqual(factorial(0), 1)\n        self.assertEqual(factorial(5), 120)\n        with self.assertRaises(ValueError): factorial(-1)\n")
        acceptance = lambda root: {
            'passed': 'math.factorial' in (root / 'solution.py').read_text(),
            'verified': True, 'tests': 1, 'output': 'factorial oracle'}
        agent = self.agent(ScriptClient([SPEC, PLAN,
            {"tool": "read_file", "args": {"path": "solution.py"}},
            {"tool": "write_file", "args": {"path": "solution.py", "content": "def factorial(n): return n\n"}},
            {"tool": "run_tests", "args": {}},
            {"diagnosis": "A implementação retorna n em vez do fatorial", "changes": ["solution.py: implementar fatorial"],
             "preserve": ["ValueError para negativos"]},
            {"tool": "write_file", "args": {"path": "solution.py", "content": "def factorial(n):\n    if n < 0: raise ValueError()\n    import math\n    return math.factorial(n)\n"}},
            {"tool": "run_tests", "args": {}},
        ]), acceptance=acceptance)
        result = agent.run("Implemente o fatorial")
        self.assertEqual(result["state"], "DONE")
        self.assertEqual(result["iterations"], 2)
        self.assertEqual(result["llm_calls"], 8)
        tests = [e["result"] for e in agent.events if e.get("tool") == "run_tests"]
        self.assertEqual([t["passed"] for t in tests], [False, True])
        self.assertTrue((agent.run_dir / "specification.md").is_file())
        self.assertTrue((agent.run_dir / "plan.md").is_file())
        self.assertEqual(json.loads((agent.run_dir / "state.json").read_text())["state"], "DONE")
        for line in (agent.run_dir / "actions.jsonl").read_text().splitlines():
            self.assertIsInstance(json.loads(line), dict)

    def test_forbidden_transitions_and_early_write(self):
        a = self.agent()
        for target in [State.IMPLEMENTING, State.DONE, State.PLANNED, State.SPECIFIED]:
            with self.assertRaises(ToolError): a.transition(target)
        with self.assertRaises(ToolError): a.call_tool("write_file", {"path": "x.py", "content": "x"})
        a.spec = SPEC
        a.transition(State.SPECIFIED)
        with self.assertRaises(ToolError): a.transition(State.IMPLEMENTING)
        with self.assertRaises(ToolError): a.transition(State.PLANNED)

    def test_done_requires_current_successful_nonempty_tests(self):
        a = self.agent()
        a.state = State.VERIFYING
        for result in [None, {"passed": False, "tests": 1, "revision": 0},
                       {"passed": True, "tests": 0, "revision": 0},
                       {"passed": True, "tests": 1, "revision": -1}]:
            a.last_test = result
            with self.assertRaises(ToolError): a.transition(State.DONE)

    def test_exhaustion_never_reports_success(self):
        a = self.agent(ScriptClient([SPEC, PLAN, {"tool": "run_tests", "args": {}}]), max_iterations=1)
        self.assertEqual(a.run("task")["state"], "FAILED")

    def test_invalid_json_retried_then_failed(self):
        a = self.agent(ScriptClient(["bad", "[]", "bad"]))
        self.assertEqual(a.run("task")["state"], "FAILED")
        self.assertEqual(a.llm_calls, 3)

    def test_rejected_responses_preserved_in_trace(self):
        malformed = 'não é JSON\n{"unfinished":'
        invalid_spec = '```json\n{ "objective": "", "acceptance_criteria": [] }\n```'
        invalid_plan = '{ "steps": [], "test_strategy": "" }'
        cases = [
            ([malformed] * 3, "json_or_size", malformed, 3),
            ([invalid_spec], "specification", invalid_spec, 1),
            ([SPEC, invalid_plan], "plan", invalid_plan, 2),
        ]
        for responses, validation, raw, call in cases:
            with self.subTest(validation=validation):
                a = self.agent(ScriptClient(responses))
                self.assertEqual(a.run("task")["state"], "FAILED")
                events = [json.loads(line) for line in
                          (a.run_dir / "actions.jsonl").read_text().splitlines()]
                rejected = [e for e in events if e["kind"] == "invalid_response"]
                self.assertEqual(rejected[-1]["raw_response"], raw)
                self.assertEqual(rejected[-1]["validation"], validation)
                self.assertEqual(rejected[-1]["llm_call"], call)
                self.assertTrue(rejected[-1]["reason"])

    def test_call_limit_is_global(self):
        a = self.agent(ScriptClient([SPEC]), max_llm_calls=1)
        self.assertEqual(a.run("task")["state"], "FAILED")
        self.assertEqual(a.llm_calls, 1)

    def test_transient_endpoint_failure_is_retried_and_counted(self):
        client = ScriptClient([TransientModelError("temporary"), SPEC, PLAN,
                               {"tool": "run_tests", "args": {}}])
        agent = self.agent(client, max_iterations=1)
        agent.run("task")
        self.assertEqual(agent.llm_calls, 4)
        retries = [event for event in agent.events if event["kind"] == "endpoint_retry"]
        self.assertEqual(len(retries), 1)

    def test_transient_endpoint_gets_five_attempts_before_failure(self):
        client = ScriptClient([TransientModelError("temporary")] * 5)
        agent = self.agent(client)
        self.assertEqual(agent.run("task")["state"], "FAILED")
        self.assertEqual(agent.llm_calls, 5)
        self.assertIn("5 chamadas", [e for e in agent.events if e["kind"] == "error"][-1]["error"])

    def test_action_limit_forces_verification(self):
        a = self.agent(ScriptClient([SPEC, PLAN, {"tool": "list_files"}]), max_actions=1, max_iterations=1)
        self.assertEqual(a.run("task")["state"], "FAILED")
        self.assertIsNotNone(a.last_test)

    def test_rejects_empty_spec_and_plan(self):
        for responses in [[{"objective": "", "acceptance_criteria": []}], [SPEC, {"steps": [], "test_strategy": ""}]]:
            a = self.agent(ScriptClient(responses))
            self.assertEqual(a.run("task")["state"], "FAILED")
            self.assertEqual(a.workspace.revision, 0)

    def test_accepts_common_specification_and_plan_envelopes(self):
        client = ScriptClient([
            {"specification": SPEC},
            {"plan": PLAN},
            {"tool": "run_tests", "args": {}},
        ])
        agent = self.agent(client, max_iterations=1)
        agent.run("task")
        self.assertEqual(agent.spec, SPEC)
        self.assertEqual(agent.plan, PLAN)
        self.assertEqual(agent.iterations, 1)

    def test_initial_context_includes_existing_test_fixtures(self):
        (self.root / "app.py").write_text("VALUE = 1\n")
        (self.root / "tests").mkdir()
        (self.root / "tests/conftest.py").write_text("@fixture_marker\n")
        client = InspectingClient([SPEC, PLAN, {"tool": "run_tests", "args": {}}])
        self.agent(client, max_iterations=1).run("task")
        first_request = client.messages[0][-1]["content"]
        self.assertIn("tests/conftest.py", first_request)
        self.assertIn("fixture_marker", first_request)

    def test_initial_context_prioritizes_file_named_by_task(self):
        (self.root / "app").mkdir()
        (self.root / "app/target.py").write_text("TARGET_MARKER = 1\n")
        (self.root / "tests").mkdir()
        for index in range(20):
            (self.root / f"tests/test_{index:02}.py").write_text("# " + "x" * 1000)
        (self.root / "tests/conftest.py").write_text("# fixture\n")
        client = InspectingClient([SPEC, PLAN, {"tool": "run_tests", "args": {}}])
        self.agent(client, max_iterations=1).run("Corrija app/target.py")
        first_request = client.messages[0][-1]["content"]
        self.assertIn("TARGET_MARKER", first_request)

    def test_forbidden_command_tool(self):
        with self.assertRaises(ToolError): self.agent().call_tool("run_command", {"command": "sudo reboot"})

    def test_replace_text_is_available_but_only_while_implementing(self):
        (self.root / "value.py").write_text("VALUE = 1\n")
        agent = self.agent()
        agent.state = State.IMPLEMENTING
        result = agent.call_tool("replace_text", {"path": "value.py", "old": "1", "new": "2"})
        self.assertEqual(result["revision"], 1)
        self.assertEqual((self.root / "value.py").read_text(), "VALUE = 2\n")

    def test_run_tests_requires_every_required_path_to_change(self):
        (self.root / "app.py").write_text("VALUE = 1\n")
        (self.root / "tests").mkdir()
        agent = self.agent(required_paths={"app.py", "tests/test_new.py"},
                           editable_paths={"app.py", "tests/test_new.py"})
        agent.state = State.IMPLEMENTING
        agent.workspace.write_file("app.py", "VALUE = 2\n")
        with self.assertRaisesRegex(ToolError, "tests/test_new.py"):
            agent.call_tool("run_tests", {})
        agent.workspace.write_file("tests/test_new.py", "def test_new(): pass\n")
        self.assertEqual(agent.required_paths - agent.workspace.changed, set())

    def test_required_changes_trigger_verification_without_another_model_call(self):
        (self.root / "app.py").write_text("VALUE = 1\n")
        (self.root / "tests").mkdir()
        client = ScriptClient([
            SPEC, PLAN,
            {"tool": "write_file", "args": {"path": "app.py", "content": "VALUE = 2\n"}},
            {"tool": "write_file", "args": {
                "path": "tests/test_new.py", "content": (
                    "import unittest\nclass T(unittest.TestCase):\n"
                    "    def test_new(self): self.assertTrue(True)\n")}},
        ])
        agent = self.agent(
            client, max_iterations=1,
            editable_paths={"app.py", "tests/test_new.py"},
            required_paths={"app.py", "tests/test_new.py"})
        result = agent.run("Mude app.py e crie o teste")
        self.assertEqual(result["state"], "DONE")
        self.assertEqual(result["llm_calls"], 4)
        self.assertTrue(any(event["kind"] == "auto_verify" for event in agent.events))

    def test_preflight_blocks_automatic_verification(self):
        (self.root / "app.py").write_text("VALUE = 1\n")
        (self.root / "tests").mkdir()
        client = ScriptClient([
            SPEC, PLAN,
            {"tool": "write_file", "args": {"path": "app.py", "content": "VALUE = 2\n"}},
            {"tool": "write_file", "args": {
                "path": "tests/test_new.py", "content": "def test_new(): assert True\n"}},
        ])
        agent = self.agent(
            client, max_actions=2, max_iterations=1,
            editable_paths={"app.py", "tests/test_new.py"},
            required_paths={"app.py", "tests/test_new.py"},
            preflight=lambda root: ["contrato ainda violado"])
        self.assertEqual(agent.run("Mude app.py e crie o teste")["state"], "FAILED")
        self.assertIsNone(agent.last_test)
        self.assertTrue(any(event["kind"] == "preflight_rejected" for event in agent.events))

    def test_repair_change_objects_are_normalized(self):
        value = [{"path": "app/controllers.py", "change": "validar parâmetros"}]
        self.assertEqual(
            Agent.normalize_repair_changes(value),
            ["app/controllers.py: validar parâmetros"])

    def test_parser(self):
        self.assertEqual(parse_object('```json\n{"x": 1}\n```'), {"x": 1})
        with self.assertRaises(ValueError): parse_object("[]")

    def test_trace_symlink_rejected(self):
        (self.root / ".minicode").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ToolError): self.agent().run("task")

    def test_unexpected_client_error_is_recorded_as_failed(self):
        class Broken:
            def complete(self,messages): raise IndexError('invalid protocol')
        agent = self.agent(Broken())
        result = agent.run('task')
        self.assertEqual(result['state'],'FAILED')
        self.assertEqual(json.loads((agent.run_dir/'state.json').read_text())['state'],'FAILED')

    def test_independent_failure_prevents_done(self):
        (self.root/'tests').mkdir()
        (self.root/'tests/test_ok.py').write_text('import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n')
        client = ScriptClient([SPEC,PLAN,{'tool':'run_tests','args':{}}])
        agent = self.agent(client,max_iterations=1,acceptance=lambda root:{'passed':False,'verified':True,'tests':1,'output':'acceptance failed'})
        self.assertEqual(agent.run('task')['state'],'FAILED')
        self.assertFalse(agent.last_test['passed'])

    def test_independent_acceptance_runs_when_project_tests_fail(self):
        (self.root / 'tests').mkdir()
        (self.root / 'tests/test_failure.py').write_text(
            'import unittest\nclass T(unittest.TestCase):\n    def test_failure(self): self.fail("candidate test")\n')
        calls = []
        acceptance = lambda root: calls.append(root) or {
            'passed': True, 'verified': True, 'tests': 1, 'output': 'independent passed'}
        client = ScriptClient([SPEC, PLAN, {'tool': 'run_tests', 'args': {}}])
        agent = self.agent(client, max_iterations=1, acceptance=acceptance)
        self.assertEqual(agent.run('task')['state'], 'FAILED')
        self.assertEqual(len(calls), 1)
        self.assertTrue(agent.last_test['acceptance']['passed'])
        self.assertFalse(agent.last_test['passed'])

    def test_passing_acceptance_freezes_production_and_leaves_new_test_editable(self):
        (self.root / 'app.py').write_text('VALUE = 1\n')
        (self.root / 'tests').mkdir()
        client = ScriptClient([
            SPEC, PLAN,
            {'tool': 'write_file', 'args': {'path': 'app.py', 'content': 'VALUE = 2\n'}},
            {'tool': 'write_file', 'args': {'path': 'tests/test_new.py', 'content': 'def test_new(): assert False\n'}},
            {'tool': 'run_tests', 'args': {}},
        ])
        agent = self.agent(client, max_iterations=1,
                           acceptance=lambda root: {'passed': True, 'verified': True, 'tests': 1, 'output': 'ok'})
        agent.run('task')
        self.assertTrue(any(event['kind'] == 'production_frozen' for event in agent.events))
        with self.assertRaisesRegex(ToolError, 'Produção aprovada'):
            agent.workspace.write_file('app.py', 'VALUE = 3\n')
        agent.workspace.write_file('tests/test_new.py', 'def test_new(): assert True\n')

    def test_repair_plan_must_follow_oracle_lock(self):
        (self.root / 'app.py').write_text('VALUE = 1\n')
        (self.root / 'tests').mkdir()
        test_bad = ('import unittest\nclass T(unittest.TestCase):\n'
                    '    def test_bad(self): self.fail("wrong candidate test")\n')
        test_good = ('import unittest\nclass T(unittest.TestCase):\n'
                     '    def test_good(self): pass\n')
        client = ScriptClient([
            SPEC, PLAN,
            {'tool': 'write_file', 'args': {'path': 'app.py', 'content': 'VALUE = 2\n'}},
            {'tool': 'write_file', 'args': {'path': 'tests/test_new.py', 'content': test_bad}},
            {'tool': 'run_tests', 'args': {}},
            {'diagnosis': 'mudar produção', 'changes': ['app.py: alterar'], 'preserve': ['contrato']},
            {'diagnosis': 'teste contradiz oráculo', 'changes': ['tests/test_new.py: corrigir'],
             'preserve': ['produção aprovada']},
            {'tool': 'write_file', 'args': {'path': 'tests/test_new.py', 'content': test_good}},
            {'tool': 'run_tests', 'args': {}},
        ])
        acceptance = lambda root: {'passed': True, 'verified': True, 'tests': 1, 'output': 'oracle ok'}
        agent = self.agent(client, max_iterations=2, acceptance=acceptance)
        self.assertEqual(agent.run('task')['state'], 'DONE')
        rejected = [event for event in agent.events if event.get('validation') == 'repair_scope']
        self.assertEqual(len(rejected), 1)

    def test_failed_acceptance_freezes_new_tests_when_production_changed(self):
        (self.root / 'app.py').write_text('VALUE = 1\n')
        (self.root / 'tests').mkdir()
        original_test = ('import unittest\nclass Original(unittest.TestCase):\n'
                         '    def test_original(self): pass\n')
        generated_test = ('import unittest\nclass Generated(unittest.TestCase):\n'
                          '    def test_new(self): pass\n')
        stronger_test = ('import unittest\nclass Generated(unittest.TestCase):\n'
                         '    def test_new(self): self.assertTrue(True)\n')
        (self.root / 'tests/test_original.py').write_text(original_test)
        client = ScriptClient([
            SPEC, PLAN,
            {'tool': 'write_file', 'args': {'path': 'app.py', 'content': 'VALUE = 2\n'}},
            {'tool': 'write_file', 'args': {'path': 'tests/test_new.py', 'content': generated_test}},
            {'tool': 'run_tests', 'args': {}},
            {'diagnosis': 'produção incorreta', 'changes': ['app.py: corrigir'], 'preserve': ['testes']},
            {'tool': 'write_file', 'args': {'path': 'tests/test_new.py', 'content': 'def test_new(): assert True\n'}},
            {'tool': 'run_tests', 'args': {}},
        ])
        acceptance = lambda root: {'passed': False, 'verified': True, 'tests': 1, 'output': 'production failed'}
        agent = self.agent(client, max_iterations=2, acceptance=acceptance)
        agent.run('task')
        rejected = [event for event in agent.events if event['kind'] == 'tool_rejected']
        self.assertTrue(any('Teste congelado' in event['error'] for event in rejected))
        self.assertTrue(any(event['kind'] == 'tests_frozen' for event in agent.events))

    def test_test_only_task_can_repair_new_tests_after_acceptance_failure(self):
        (self.root / 'tests').mkdir()
        client = ScriptClient([
            SPEC, PLAN,
            {'tool': 'write_file', 'args': {'path': 'tests/test_new.py', 'content': 'def test_new(): pass\n'}},
            {'tool': 'run_tests', 'args': {}},
            {'diagnosis': 'teste fraco', 'changes': ['tests/test_new.py: fortalecer'], 'preserve': ['aplicação']},
            {'tool': 'write_file', 'args': {'path': 'tests/test_new.py', 'content': 'def test_new(): assert True\n'}},
            {'tool': 'run_tests', 'args': {}},
        ])
        acceptance = lambda root: {'passed': False, 'verified': True, 'tests': 1, 'output': 'mutation survived'}
        agent = self.agent(client, max_iterations=2, acceptance=acceptance)
        agent.run('task')
        self.assertEqual((self.root / 'tests/test_new.py').read_text(), 'def test_new(): assert True\n')
        self.assertFalse(any(event['kind'] == 'tests_frozen' for event in agent.events))

    def test_passing_acceptance_unfreezes_only_generated_tests(self):
        (self.root / 'app.py').write_text('VALUE = 1\n')
        (self.root / 'tests').mkdir()
        original_test = ('import unittest\nclass Original(unittest.TestCase):\n'
                         '    def test_original(self): pass\n')
        generated_test = ('import unittest\nclass Generated(unittest.TestCase):\n'
                          '    def test_new(self): pass\n')
        stronger_test = ('import unittest\nclass Generated(unittest.TestCase):\n'
                         '    def test_new(self): self.assertTrue(True)\n')
        (self.root / 'tests/test_original.py').write_text(original_test)
        client = ScriptClient([
            SPEC, PLAN,
            {'tool': 'write_file', 'args': {'path': 'app.py', 'content': 'VALUE = 2\n'}},
            {'tool': 'write_file', 'args': {'path': 'tests/test_new.py', 'content': generated_test}},
            {'tool': 'run_tests', 'args': {}},
            {'diagnosis': 'corrigir produção', 'changes': ['app.py'], 'preserve': ['testes']},
            {'tool': 'write_file', 'args': {'path': 'app.py', 'content': 'VALUE = 3\n'}},
            {'tool': 'run_tests', 'args': {}},
        ])
        results = iter([
            {'passed': False, 'verified': True, 'tests': 1, 'output': 'failed'},
            {'passed': True, 'verified': True, 'tests': 1, 'output': 'passed'},
        ])
        agent = self.agent(client, max_iterations=2, acceptance=lambda root: next(results))
        result = agent.run('task')
        self.assertEqual(result['state'], 'DONE', (agent.last_test, agent.events))
        self.assertTrue(any(event['kind'] == 'tests_frozen' for event in agent.events))
        self.assertTrue(any(event['kind'] == 'tests_unfrozen' for event in agent.events))
        agent.workspace.write_file('tests/test_new.py', stronger_test)
        with self.assertRaisesRegex(ToolError, 'protegidos'):
            agent.workspace.write_file('tests/test_original.py', stronger_test)

    def test_full_output_is_available_by_pages(self):
        agent = self.agent()
        agent.last_test = {'output':'a'*20000+'FINAL ERROR'}
        preview = agent.feedback(agent.last_test)
        self.assertIn('FINAL ERROR',preview)
        self.assertIn('trecho intermediário omitido',preview)
        page = agent.call_tool('read_test_output',{'offset':19000})
        self.assertTrue(page['output'].endswith('FINAL ERROR'))

    def test_feedback_preserves_project_and_acceptance_beginnings(self):
        agent = self.agent()
        value = {
            'output': 'PROJECT-START\n' + 'p' * 10000 + '\nPROJECT-END',
            'acceptance': {
                'passed': False, 'verified': True, 'tests': 2,
                'output': 'ACCEPTANCE-START\n' + 'a' * 10000 + '\nACCEPTANCE-END',
            },
        }
        compact = json.loads(agent.feedback(value))
        self.assertIn('PROJECT-START', compact['output'])
        self.assertIn('PROJECT-END', compact['output'])
        self.assertIn('ACCEPTANCE-START', compact['independent_acceptance']['output'])
        self.assertIn('ACCEPTANCE-END', compact['independent_acceptance']['output'])

    def test_mutation_feedback_explains_that_mutant_failures_are_positive(self):
        agent = self.agent()
        value = {
            'output': 'candidate failed on original',
            'acceptance': {
                'passed': False, 'verified': True, 'tests': 3, 'killed': 4, 'total': 4,
                'trials': [
                    {'passed': False, 'output': 'ORIGINAL FAILURE'},
                    {'passed': False, 'output': 'EXPECTED MUTANT FAILURE'},
                ],
                'output': 'all trial details',
            },
        }
        compact = json.loads(agent.feedback(value))['independent_acceptance']
        self.assertIn('ORIGINAL FAILURE', compact['output'])
        self.assertNotIn('EXPECTED MUTANT FAILURE', compact['output'])
        self.assertEqual(compact['mutation']['mutants_killed'], 4)
        self.assertIn('resultados positivos', compact['mutation']['guidance'])

    def test_repair_plan_is_recorded_before_second_attempt(self):
        (self.root / 'tests').mkdir()
        (self.root / 'tests/test_failure.py').write_text(
            'import unittest\nclass T(unittest.TestCase):\n    def test_failure(self): self.fail("first")\n')
        client = ScriptClient([
            SPEC, PLAN, {'tool': 'run_tests', 'args': {}},
            {'diagnosis': 'teste falha', 'changes': ['tests/test_new.py: corrigir cenário'], 'preserve': ['contrato']},
            {'tool': 'run_tests', 'args': {}},
        ])
        agent = self.agent(client, max_iterations=2)
        agent.run('task')
        plans = [event for event in agent.events if event['kind'] == 'repair_plan']
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['iteration'], 1)
        resets = [event for event in agent.events if event['kind'] == 'repair_context_reset']
        self.assertEqual(len(resets), 1)

    def test_repair_request_uses_fresh_current_file_context(self):
        (self.root / 'app.py').write_text('VALUE = 1\n')
        (self.root / 'tests').mkdir()
        (self.root / 'tests/test_failure.py').write_text(
            'import unittest\nclass T(unittest.TestCase):\n    def test_failure(self): self.fail("bad")\n')
        client = InspectingClient([
            SPEC, PLAN,
            {'tool': 'write_file', 'args': {'path': 'app.py', 'content': 'VALUE = 2\n'}},
            {'tool': 'run_tests', 'args': {}},
            {'diagnosis': 'valor ainda incorreto', 'changes': ['app.py: corrigir'],
             'preserve': ['API']},
            {'tool': 'run_tests', 'args': {}},
        ])
        agent = self.agent(
            client, max_iterations=2, editable_paths={'app.py'},
            acceptance=lambda root: {'passed': False, 'verified': True, 'tests': 1,
                                     'output': 'production failed'})
        agent.run('Ajuste app.py')
        repair_messages = client.messages[4]
        self.assertEqual(len(repair_messages), 3)
        self.assertIn('VALUE = 2', repair_messages[-1]['content'])
        self.assertIn('Arquivos atuais que podem ser reparados', repair_messages[-1]['content'])

    def test_done_requires_independent_acceptance(self):
        (self.root/'tests').mkdir()
        (self.root/'tests/test_ok.py').write_text('import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n')
        client = ScriptClient([SPEC,PLAN,{'tool':'run_tests','args':{}}])
        agent = self.agent(client,max_iterations=1,acceptance=None)
        self.assertEqual(agent.run('task')['state'],'FAILED')
        self.assertIn('independente',agent.last_test['error'])
