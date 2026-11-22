#!/usr/bin/env python3
"""Score prediction JSONL without loading training dependencies.

Predictions must contain id and tool. This makes base/LoRA/Qwen runs auditable
and prevents a notebook from accidentally evaluating the training split.
"""
import argparse
import json
from pathlib import Path
from minicode.specialization_data import load_examples, validate_examples
from minicode.tool_selector import TOOLS

def read_predictions(path):
    result = {}
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        row = json.loads(line)
        if not isinstance(row.get("id"), str) or row.get("tool") not in TOOLS or row["id"] in result:
            raise ValueError(f"Predição inválida na linha {number}")
        result[row["id"]] = row["tool"]
    return result

def evaluate(dataset, predictions, split="test"):
    rows = [row for row in dataset if row["split"] == split]
    expected = {row["id"] for row in rows}
    if set(predictions) != expected:
        raise ValueError("Predições devem cobrir exatamente o split avaliado")
    correct = sum(predictions[row["id"]] == row["label"] for row in rows)
    return {"split": split, "examples": len(rows), "correct": correct,
            "accuracy": correct / len(rows), "per_example": [
                {"id": row["id"], "gold": row["label"], "predicted": predictions[row["id"]],
                 "correct": predictions[row["id"]] == row["label"]} for row in rows]}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/tool_selection/examples.jsonl")
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
