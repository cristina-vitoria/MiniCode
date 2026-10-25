import json
from pathlib import Path
import tempfile
import unittest

from minicode.agent import Agent, State
from minicode.llm import parse_object
from minicode.tools import TestRunner, ToolError


class ScriptClient:
    def __init__(self, values):
        self.values = iter(values)
    def complete(self, messages):
        value = next(self.values)
        return value if isinstance(value, str) else json.dumps(value)


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
        agent = self.agent(ScriptClient([SPEC, PLAN,
            {"tool": "read_file", "args": {"path": "solution.py"}},
            {"tool": "write_file", "args": {"path": "solution.py", "content": "def factorial(n): return n\n"}},
            {"tool": "run_tests", "args": {}},
            {"tool": "write_file", "args": {"path": "solution.py", "content": "def factorial(n):\n    if n < 0: raise ValueError()\n    import math\n    return math.factorial(n)\n"}},
            {"tool": "run_tests", "args": {}},
        ]))
        result = agent.run("Implemente o fatorial")
        self.assertEqual(result["state"], "DONE")
        self.assertEqual(result["iterations"], 2)
        self.assertEqual(result["llm_calls"], 7)
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

    def test_action_limit_forces_verification(self):
        a = self.agent(ScriptClient([SPEC, PLAN, {"tool": "list_files"}]), max_actions=1, max_iterations=1)
        self.assertEqual(a.run("task")["state"], "FAILED")
        self.assertIsNotNone(a.last_test)

    def test_rejects_empty_spec_and_plan(self):
        for responses in [[{"objective": "", "acceptance_criteria": []}], [SPEC, {"steps": [], "test_strategy": ""}]]:
            a = self.agent(ScriptClient(responses))
            self.assertEqual(a.run("task")["state"], "FAILED")
            self.assertEqual(a.workspace.revision, 0)

    def test_forbidden_command_tool(self):
        with self.assertRaises(ToolError): self.agent().call_tool("run_command", {"command": "sudo reboot"})

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

    def test_full_output_is_available_by_pages(self):
        agent = self.agent()
        agent.last_test = {'output':'a'*20000+'FINAL ERROR'}
        preview = agent.feedback(agent.last_test)
        self.assertIn('FINAL ERROR',preview)
        self.assertIn('truncado',preview)
        page = agent.call_tool('read_test_output',{'offset':19000})
        self.assertTrue(page['output'].endswith('FINAL ERROR'))

    def test_done_requires_independent_acceptance(self):
        (self.root/'tests').mkdir()
        (self.root/'tests/test_ok.py').write_text('import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n')
        client = ScriptClient([SPEC,PLAN,{'tool':'run_tests','args':{}}])
        agent = self.agent(client,max_iterations=1,acceptance=None)
        self.assertEqual(agent.run('task')['state'],'FAILED')
        self.assertIn('independente',agent.last_test['error'])
