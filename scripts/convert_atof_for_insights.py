#!/usr/bin/env python3
"""Convert a real Relay ATOF stream into standalone Insights Trace JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pa_style_mock_mcp.insights import atof_events_to_insights_traces  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--atof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--matrix", type=Path)
    args = parser.parse_args()

    events = [json.loads(line) for line in args.atof.read_text().splitlines() if line.strip()]
    prompt_case_ids = None
    case_required_signals = None
    if args.matrix:
        matrix = json.loads(args.matrix.read_text())
        prompt_case_ids = {scenario["prompt"]: scenario["id"] for scenario in matrix["scenarios"]}
        case_required_signals = {
            scenario["id"]: scenario.get("signals", []) for scenario in matrix["scenarios"]
        }
    traces = atof_events_to_insights_traces(
        events,
        prompt_case_ids=prompt_case_ids,
        case_required_signals=case_required_signals,
    )
    if not traces:
        raise SystemExit("no completed hermes.turn scopes found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(trace, separators=(",", ":")) + "\n" for trace in traces))
    print(f"Converted {len(traces)} completed Hermes turns to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
