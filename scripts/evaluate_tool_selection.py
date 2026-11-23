#!/usr/bin/env python3
"""Score prediction JSONL without loading training dependencies.

Predictions must contain id and tool. This makes base/LoRA/Qwen runs auditable
and prevents a notebook from accidentally evaluating the training split.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minicode.specialization_data import load_examples, validate_examples
from minicode.tool_selector import TOOLS

def read_predictions(path):
    result = {}
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON inválido na linha {number}: {exc.msg}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"Predição na linha {number} deve ser um objeto JSON")
        if not isinstance(row.get("id"), str):
            raise ValueError(f"Campo 'id' inválido na linha {number}: {row.get('id')!r}")
        if not isinstance(row.get("tool"), str):
            raise ValueError(f"Campo 'tool' inválido na linha {number}: {row.get('tool')!r}")
        if row["id"] in result:
            raise ValueError(f"ID duplicado na linha {number}: {row['id']!r}")
        result[row["id"]] = row["tool"]
    return result

def evaluate(dataset, predictions, split="test"):
    rows = [row for row in dataset if row["split"] == split]
    expected = {row["id"] for row in rows}
    if set(predictions) != expected:
        raise ValueError("Predições devem cobrir exatamente o split avaliado")
    correct = sum(predictions[row["id"]] == row["label"] for row in rows)
    invalid = sum(predictions[row["id"]] not in TOOLS for row in rows)
    return {"split": split, "examples": len(rows), "correct": correct,
            "accuracy": correct / len(rows), "invalid_predictions": invalid,
            "per_example": [
                {"id": row["id"], "gold": row["label"], "predicted": predictions[row["id"]],
                 "valid_tool": predictions[row["id"]] in TOOLS,
                 "correct": predictions[row["id"]] == row["label"]} for row in rows]}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(ROOT / "data/tool_selection/examples.jsonl"))
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--split", choices=["validation", "test"], default="test")
    parser.add_argument("--output")
    args = parser.parse_args()
    dataset = load_examples(args.dataset)
    validate_examples(dataset)
    report = evaluate(dataset, read_predictions(args.predictions), args.split)
    serialized = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output: Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
