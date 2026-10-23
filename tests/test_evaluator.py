import unittest
from minicode.benchmark import CASES, test_source
from minicode.evaluator import metrics


class EvaluationTests(unittest.TestCase):
    def test_metrics_include_failures(self):
        rows = [{"success": True, "iterations": 1, "llm_calls": 4},
                {"success": True, "iterations": 2, "llm_calls": 8},
                {"success": False, "iterations": 3, "llm_calls": 9}]
        result = metrics(rows)
        self.assertAlmostEqual(result["TaskSuccessRate"], 2/3)
        self.assertAlmostEqual(result["FirstAttemptSuccess"], 1/3)
        self.assertEqual(result["AverageIterations"], 2)
        self.assertEqual(result["AverageLLMCalls"], 7)
        self.assertEqual(metrics([])["total_tasks"], 0)

    def test_six_categories_and_valid_oracles(self):
        self.assertEqual(len({c["kind"] for c in CASES}), 6)
        for case in CASES:
            compile(case["source"], case["id"], "exec")
            compile(test_source(case["checks"]), case["id"], "exec")

    def test_full_evaluator_with_scripted_solutions(self):
        import json
        from pathlib import Path
        import tempfile
        from minicode.evaluator import evaluate

        solutions = [
            "def factorial(n):\n    if n < 0: raise ValueError()\n    import math\n    return math.factorial(n)\n",
            "def mean(values):\n    if not values: raise ValueError()\n    return sum(values) / len(values)\n",
            "def app(environ, start_response):\n    if environ['PATH_INFO'] == '/health' and environ['REQUEST_METHOD'] == 'GET':\n        start_response('200 OK', [('Content-Type', 'application/json')])\n        return [b'{\"status\":\"ok\"}']\n    start_response('404 Not Found', [])\n    return [b'not found']\n",
            CASES[3]["source"],
            "def validate_age(value):\n    if type(value) is not int or not 0 <= value <= 130: raise ValueError()\n    return value\n",
            "def subtotal(item):\n    return item['price'] * item['quantity']\ndef total_price(items):\n    return sum(subtotal(item) for item in items)\n",
        ]
        cases = iter(zip(CASES, solutions))
        class Client:
            def __init__(self, responses): self.responses = iter(responses)
            def complete(self, messages): return json.dumps(next(self.responses))
        def factory():
            case, solution = next(cases)
            return Client([
                {"objective": case["task"], "acceptance_criteria": ["Atender critérios da tarefa"]},
                {"steps": ["Implementar", "Testar"], "test_strategy": "unittest"},
                {"tool": "write_file", "args": {"path": "solution.py", "content": solution}},
                {"tool": "write_file", "args": {"path": "tests/test_clamp.py" if case["id"] == "tests" else "tests/test_generated.py", "content": test_source(case["checks"])}},
                {"tool": "run_tests", "args": {}},
            ])
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate(factory, Path(tmp) / "results", "local")
            self.assertEqual(result["metrics"]["TaskSuccessRate"], 1)
            self.assertEqual(result["metrics"]["AverageLLMCalls"], 5)
            self.assertEqual(result["tasks"][3]["mutation"]["killed"], 4)
            self.assertTrue((Path(tmp) / "results/results.json").is_file())
