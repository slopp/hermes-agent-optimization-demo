#!/usr/bin/env python3
"""Combine reviewed per-case ATIF extracts into one scored eval arm.

This script deliberately accepts only extracted runs, never raw ATIF or
hand-authored trajectories. Each input file represents one real agent run
that has already passed through ``extract_atif_run.py``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_run(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON: {error.msg}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a single run object")

    case_id = value.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError(f"{path}: run must contain a non-empty case_id")
    for field, value_type in (("calls", list), ("outbox", list), ("final_answer", str)):
        if not isinstance(value.get(field), value_type):
            raise ValueError(f"{path}: run field {field!r} must be a {value_type.__name__}")
    return value


def assemble_runs(input_dir: Path) -> list[dict]:
    if not input_dir.is_dir():
        raise ValueError(f"input directory does not exist: {input_dir}")
    paths = sorted(input_dir.glob("*.json"))
    if not paths:
        raise ValueError(f"no JSON run files found in: {input_dir}")

    runs = [load_run(path) for path in paths]
    ids = [run["case_id"] for run in runs]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise ValueError(f"duplicate case_id values: {', '.join(duplicates)}")
    return sorted(runs, key=lambda run: run["case_id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True, help="Directory of one extracted JSON run per case")
    parser.add_argument("--output", type=Path, required=True, help="Combined JSON list for score_eval_runs.py")
    args = parser.parse_args()

    runs = assemble_runs(args.input_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(runs, indent=2) + "\n")
    print(f"Assembled {len(runs)} unique case runs into {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        raise SystemExit(f"error: {error}")
