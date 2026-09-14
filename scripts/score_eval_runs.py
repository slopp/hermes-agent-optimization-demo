#!/usr/bin/env python3
"""Score a complete recorded run file and optionally compare two arms.

Example:
  PYTHONPATH=src python scripts/score_eval_runs.py \
    --suite evals/trace-derived-suite.json --runs artifacts/baseline-runs.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pa_style_mock_mcp.eval_runner import compare_reports, score_runs  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True, help="JSON list of extracted real agent runs")
    parser.add_argument("--compare-runs", type=Path, help="Optional candidate arm to compare against --runs")
    parser.add_argument("--output", type=Path, help="Optional JSON report output path")
    args = parser.parse_args()

    baseline = score_runs(load(args.suite), load(args.runs))
    report = {"baseline": baseline}
    if args.compare_runs:
        candidate = score_runs(load(args.suite), load(args.compare_runs))
        report["candidate"] = candidate
        report["comparison"] = compare_reports(baseline, candidate)

    encoded = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n")
        print(f"Wrote score report to {args.output}")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
