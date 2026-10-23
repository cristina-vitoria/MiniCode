"""Avaliação em cópias isoladas; os oráculos são instalados só após o agente terminar."""
import json
from pathlib import Path
import shutil
import tempfile
import time

from .agent import Agent
from .benchmark import CASES, test_source
from .tools import TestRunner


def metrics(rows):
    n = len(rows)
    return {"total_tasks": n,
            "TaskSuccessRate": sum(r["success"] for r in rows) / n if n else 0,
            "FirstAttemptSuccess": sum(r["success"] and r["iterations"] == 1 for r in rows) / n if n else 0,
            "AverageIterations": sum(r["iterations"] for r in rows) / n if n else 0,
            "AverageLLMCalls": sum(r["llm_calls"] for r in rows) / n if n else 0}


def evaluate(client_factory, output, mode="docker", max_iterations=3,
             max_actions=20, max_llm_calls=80, timeout=30):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for case in CASES:
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="minicode-eval-") as tmp:
            root = Path(tmp)
            (root / "solution.py").write_text(case["source"])
            (root / "tests").mkdir()
            (root / "tests" / "test_smoke.py").write_text("import unittest\nimport solution\nclass Smoke(unittest.TestCase):\n    def test_import(self):\n        self.assertIsNotNone(solution)\n")
            agent = Agent(root, client_factory(), TestRunner(root, mode, timeout),
                          max_iterations=max_iterations, max_actions=max_actions,
                          max_llm_calls=max_llm_calls)
            result = agent.run(case["task"])
            # Snapshot final preserva rastros, código e testes gerados; oráculo em diretório separado.
            saved = output / case["id"]
            shutil.copytree(root, saved)
            with tempfile.TemporaryDirectory(prefix="minicode-oracle-") as oracle_dir:
                oracle = Path(oracle_dir)
                shutil.copy(root / "solution.py", oracle / "solution.py")
                (oracle / "tests").mkdir()
                (oracle / "tests" / "test_acceptance.py").write_text(test_source(case["checks"]))
                acceptance = TestRunner(oracle, mode, timeout).run()
                mutation = None
                if case["id"] == "tests":
                    generated = root / "tests" / "test_clamp.py"
                    mutation = {"created": generated.is_file(), "killed": 0, "total": 4}
                    if generated.is_file():
                        (oracle / "tests" / "test_acceptance.py").unlink()
                        shutil.copy(generated, oracle / "tests" / "test_clamp.py")
                        baseline = TestRunner(oracle, mode, timeout).run()
                        mutants = ["return x", "return low", "return high", "return max(low, min(x, high))"]
                        for code in mutants:
                            (oracle / "solution.py").write_text("def clamp(x, low, high):\n    " + code + "\n")
                            trial = TestRunner(oracle, mode, timeout).run()
                            if trial.get("tests", 0) > 0 and trial.get("returncode") == 1 and not trial.get("timed_out"):
                                mutation["killed"] += 1
                        acceptance["passed"] = acceptance["passed"] and baseline["passed"] and mutation["killed"] == 4
                    else:
                        acceptance["passed"] = False
            rows.append({"id": case["id"], "kind": case["kind"], **result,
                         "trace": str(saved / ".minicode" / Path(result["trace"]).name),
                         "success": result["state"] == "DONE" and acceptance["passed"],
                         "acceptance": acceptance, "mutation": mutation, "seconds": time.monotonic() - start})
            (output / "results.json").write_text(json.dumps({"metrics": metrics(rows), "tasks": rows}, indent=2, ensure_ascii=False))
    return {"metrics": metrics(rows), "tasks": rows}
