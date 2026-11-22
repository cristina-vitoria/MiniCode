"""Dataset validation and leakage-resistant split checks for Parte 2."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .tool_selector import TOOLS

REQUIRED_INPUT = {"state", "task", "specification", "plan", "feedback"}
SPLITS = {"train", "validation", "test"}


def load_examples(path: str | Path) -> list[dict]:
    rows = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON inválido na linha {line_no}") from exc
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not isinstance(row.get("task_family"), str):
            raise ValueError(f"id/task_family inválidos na linha {line_no}")
        if row.get("split") not in SPLITS or row.get("label") not in TOOLS:
            raise ValueError(f"split ou rótulo inválido na linha {line_no}")
        if not isinstance(row.get("input"), dict) or REQUIRED_INPUT - set(row["input"]):
            raise ValueError(f"entrada incompleta na linha {line_no}")
        rows.append(row)
    if not rows:
        raise ValueError("Dataset vazio")
    return rows


def validate_examples(rows: list[dict]) -> dict:
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("IDs duplicados")
    family_split = {}
    for row in rows:
        family_split.setdefault(row["task_family"], row["split"])
        if family_split[row["task_family"]] != row["split"]:
            raise ValueError("Vazamento: uma família aparece em mais de um split")
    counts = Counter(row["split"] for row in rows)
    if any(not counts[split] for split in SPLITS):
        raise ValueError("train, validation e test precisam conter exemplos")
    return {"examples": len(rows), "families": len(family_split), "by_split": dict(sorted(counts.items())),
            "families_by_split": {split: sorted(f for f, s in family_split.items() if s == split) for split in sorted(SPLITS)}}


def validate_file(path: str | Path) -> dict:
    return validate_examples(load_examples(path))
