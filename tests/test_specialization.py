import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from minicode.specialization_data import load_examples, validate_examples
from minicode.tool_selector import FixedToolSelector, OpenAICompatibleToolSelector, TOOLS
from minicode.agent import Agent
from minicode.llm import ModelError
from minicode.selector_protocol import parse_tool_name, selector_payload, selector_prompt, selector_messages, training_record
from minicode.tools import TestRunner


ROOT = Path(__file__).resolve().parents[1]
SPEC = {"objective": "Objetivo", "acceptance_criteria": ["Retorna 1"]}
PLAN = {"steps": ["Implementar"], "test_strategy": "unittest"}


class ScriptClient:
    def __init__(self, values): self.values = iter(values)
    def complete(self, _): return json.dumps(next(self.values))


class SpecializationDataTests(unittest.TestCase):
    def test_supervised_target_and_inference_prefix_are_identical(self):
        rows = load_examples(ROOT / 'data/tool_selection/examples.jsonl')
        for row in rows:
            record = training_record(row)
            self.assertEqual(record['prompt'], selector_messages(**row['input']))
            self.assertEqual(record['completion'], [{'role':'assistant','content':row['label']}])
            self.assertEqual(record['prompt'][-1]['role'], 'user')

    def test_selector_calls_consume_global_budget_even_on_failure(self):
        class FailedSelector:
            def select(self, **kwargs):
                raise ModelError('selector unavailable')
        with tempfile.TemporaryDirectory() as temp:
            agent = Agent(Path(temp), ScriptClient([SPEC, PLAN]),
                TestRunner(temp, 'local', 1), tool_selector=FailedSelector(),
                max_llm_calls=3, max_iterations=1)
            result = agent.run('tarefa')
            self.assertEqual(result['state'], 'FAILED')
            self.assertEqual(result['llm_calls'], 3)
            self.assertEqual(result['selector_calls'], 1)
            state = json.loads((agent.run_dir/'state.json').read_text())
            self.assertEqual(state['selector_calls'], 1)

    def test_selector_cannot_start_after_global_budget(self):
        class ForbiddenSelector:
            def select(self, **kwargs):
                raise AssertionError('selector must not be invoked')
        with tempfile.TemporaryDirectory() as temp:
            agent = Agent(Path(temp), ScriptClient([SPEC, PLAN]),
                TestRunner(temp, 'local', 1), tool_selector=ForbiddenSelector(),
                max_llm_calls=2, max_iterations=1)
            result = agent.run('tarefa')
            self.assertEqual(result['state'], 'FAILED')
            self.assertEqual(result['llm_calls'], 2)
            self.assertEqual(result['selector_calls'], 0)

    def test_curated_dataset_is_valid_and_group_disjoint(self):
        report = validate_examples(load_examples(ROOT / "data/tool_selection/examples.jsonl"))
        self.assertEqual(report["by_split"], {"test": 16, "train": 64, "validation": 16})
        self.assertEqual(report["families_by_split"]["test"], ["audit_logging", "retry_timeout"])

    def test_rejects_family_leakage(self):
        rows = [
            {"id": "a", "task_family": "same", "split": "train", "label": "read_file", "input": {k: {} for k in ["state", "task", "specification", "plan", "feedback"]}},
            {"id": "b", "task_family": "same", "split": "test", "label": "read_file", "input": {k: {} for k in ["state", "task", "specification", "plan", "feedback"]}},
        ]
        with self.assertRaisesRegex(ValueError, "Vazamento"):
            validate_examples(rows)

    def test_evaluator_runs_outside_repository(self):
        rows = load_examples(ROOT / "data/tool_selection/examples.jsonl")
        predictions = [
            {"id": row["id"], "tool": row["label"]}
            for row in rows
            if row["split"] == "test"
        ]
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            predictions_path = temp_path / "predictions.jsonl"
            output_path = temp_path / "report.json"
            predictions_path.write_text(
                "\n".join(json.dumps(row) for row in predictions) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/evaluate_tool_selection.py"),
                    "--predictions",
                    str(predictions_path),
                    "--output",
                    str(output_path),
                ],
                cwd=temp_path,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output_path.read_text())["accuracy"], 1.0)

            predictions[0]["tool"] = "invalid_tool"
            predictions_path.write_text(
                "\n".join(json.dumps(row) for row in predictions) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/evaluate_tool_selection.py"),
                    "--predictions",
                    str(predictions_path),
                    "--output",
                    str(output_path),
                ],
                cwd=temp_path,
                capture_output=True,
                text=True,
            )
            report = json.loads(output_path.read_text())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(report["accuracy"], (len(predictions) - 1) / len(predictions))
            self.assertEqual(report["invalid_predictions"], 1)

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

    def test_training_and_production_share_plain_tool_protocol(self):
        payload = selector_payload(
            state="IMPLEMENTING", task="corrija", specification={"objective": "x"},
            plan={"steps": ["ler"]}, feedback="início",
        )
        prompt = selector_prompt(payload)
        self.assertIn('"allowed_tools"', prompt)
        self.assertEqual(parse_tool_name("read_file\n"), "read_file")
        with self.assertRaises(ValueError):
            parse_tool_name('{"tool":"read_file"}')

        class PlainClient:
            def complete(self, messages):
                self.messages = messages
                return "read_file"

        client = PlainClient()
        decision = OpenAICompatibleToolSelector(client).select(
            state="IMPLEMENTING", task="corrija", specification={}, plan={}, feedback="início",
        )
        self.assertEqual(decision.tool, "read_file")
        expected = selector_prompt(selector_payload(
            state="IMPLEMENTING", task="corrija", specification={}, plan={}, feedback="início",
        ))
        self.assertEqual(client.messages[-1]["content"], expected)

        without_context = OpenAICompatibleToolSelector(client, include_context=False)
        without_context.select(
            state="IMPLEMENTING", task="corrija",
            specification={"objective": "não deve aparecer"},
            plan={"steps": ["não deve aparecer"]}, feedback="início",
        )
        self.assertNotIn("não deve aparecer", client.messages[-1]["content"])

    def test_specialized_selector_rejects_noncanonical_output(self):
        class InvalidClient:
            def complete(self, _): return '{"tool":"read_file"}'

        with self.assertRaises(ModelError):
            OpenAICompatibleToolSelector(InvalidClient()).select(
                state="IMPLEMENTING", task="x", specification={}, plan={}, feedback="x",
            )
