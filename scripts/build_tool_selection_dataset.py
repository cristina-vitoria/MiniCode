#!/usr/bin/env python3
"""Build a small, auditable seed dataset; no teacher call is made here."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "tool_selection" / "examples.jsonl"

# Distinct task families are the split unit. Labels describe the next safe
# operational step, not arguments and not an authorization to execute it.
FAMILIES = {
    "discount": [("IMPLEMENTING", "read_file"), ("IMPLEMENTING", "replace_python_function"), ("IMPLEMENTING", "write_file"), ("IMPLEMENTING", "run_tests")],
    "tax": [("IMPLEMENTING", "search_code"), ("IMPLEMENTING", "read_file"), ("IMPLEMENTING", "replace_text"), ("IMPLEMENTING", "run_tests")],
    "pagination": [("IMPLEMENTING", "read_file"), ("IMPLEMENTING", "search_code"), ("IMPLEMENTING", "replace_python_function"), ("REPAIRING", "read_test_output")],
    "tests": [("IMPLEMENTING", "read_file"), ("IMPLEMENTING", "write_file"), ("IMPLEMENTING", "run_tests"), ("REPAIRING", "replace_text")],
    "users": [("IMPLEMENTING", "list_files"), ("IMPLEMENTING", "read_file"), ("IMPLEMENTING", "replace_python_function"), ("IMPLEMENTING", "run_tests")],
    "refactor": [("IMPLEMENTING", "search_code"), ("IMPLEMENTING", "read_file"), ("IMPLEMENTING", "replace_python_function"), ("IMPLEMENTING", "run_tests")],
}
SPLITS = {"discount": "train", "tax": "train", "tests": "train", "users": "train", "refactor": "validation", "pagination": "test"}

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for family, actions in FAMILIES.items():
        for step, (state, tool) in enumerate(actions, 1):
            rows.append({
                "id": f"{family}-{step}", "task_family": family, "split": SPLITS[family],
                "input": {"state": state, "task": f"Tarefa {family}: etapa {step}",
                          "specification": {"objective": f"Concluir {family}"},
                          "plan": {"steps": ["inspecionar", "alterar", "verificar"]},
                          "feedback": "Sem erro anterior."},
                "label": tool,
                "provenance": "curated_from_part1_contract",
            })
    with OUT.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    main()
