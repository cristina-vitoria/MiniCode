import json
from pathlib import Path
import tempfile
import unittest

from minicode.specialization_data import load_examples, validate_examples
from minicode.tool_selector import FixedToolSelector, TOOLS
from minicode.agent import Agent
from minicode.tools import TestRunner


ROOT = Path(__file__).resolve().parents[1]
SPEC = {"objective": "Objetivo", "acceptance_criteria": ["Retorna 1"]}
PLAN = {"steps": ["Implementar"], "test_strategy": "unittest"}


class ScriptClient:
    def __init__(self, values): self.values = iter(values)
    def complete(self, _): return json.dumps(next(self.values))


class SpecializationDataTests(unittest.TestCase):
    def test_curated_dataset_is_valid_and_group_disjoint(self):
        report = validate_examples(load_examples(ROOT / "data/tool_selection/examples.jsonl"))
        self.assertEqual(report["by_split"], {"test": 4, "train": 16, "validation": 4})
        self.assertEqual(report["families_by_split"]["test"], ["pagination"])

    def test_rejects_family_leakage(self):
        rows = [
            {"id": "a", "task_family": "same", "split": "train", "label": "read_file", "input": {k: {} for k in ["state", "task", "specification", "plan", "feedback"]}},
            {"id": "b", "task_family": "same", "split": "test", "label": "read_file", "input": {k: {} for k in ["state", "task", "specification", "plan", "feedback"]}},
        ]
        with self.assertRaisesRegex(ValueError, "Vazamento"):
            validate_examples(rows)

    def test_selector_cannot_bypass_tool_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            selector = FixedToolSelector(["run_tests"])
            agent = Agent(root, ScriptClient([SPEC, PLAN, {"tool": "write_file", "args": {"path": "x.py", "content": "x=1"}}]),
                          TestRunner(root, "local", 1), acceptance=lambda _: {"passed": True, "verified": True, "tests": 1},
                          tool_selector=selector, max_iterations=1)
            result = agent.run("tarefa")
            self.assertEqual(result["state"], "FAILED")
            self.assertFalse((root / "x.py").exists())
            self.assertTrue(any(e["kind"] == "tool_selection_rejected" for e in agent.events))
