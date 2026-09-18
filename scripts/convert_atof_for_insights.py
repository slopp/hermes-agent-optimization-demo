#!/usr/bin/env python3
"""Convert a real Relay ATOF stream into standalone Insights Trace JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pa_style_mock_mcp.insights import atof_events_to_insights_traces
from pa_style_mock_mcp.jsonl import read_relay_jsonl


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--atof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--matrix", type=Path)
    parser.add_argument(
        "--include-incomplete",
        action="store_true",
        help="Include bounded Hermes turns without a closing Relay event as scored failures.",
    )
    args = parser.parse_args()

    events, recovered_lines = read_relay_jsonl(args.atof)
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
        include_incomplete=args.include_incomplete,
    )
    if not traces:
        raise SystemExit("no completed hermes.turn scopes found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(trace, separators=(",", ":")) + "\n" for trace in traces))
    if recovered_lines:
        print(f"Recovered complete records after interrupted writes on lines {recovered_lines}")
    print(f"Converted {len(traces)} Hermes turns to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
