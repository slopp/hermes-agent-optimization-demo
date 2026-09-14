#!/usr/bin/env python3
"""Check that collected real ATIF runs cover the public fidelity matrix signals.

This is a pre-Insights completeness check only. A matching tool sequence is not
evidence that an agent failure occurred, nor that a harness change is correct.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pa_style_mock_mcp.atif import extract_run  # noqa: E402


def is_subsequence(expected: list[str], observed: list[str]) -> bool:
    """Return true when expected signals occur in order, with gaps allowed."""
    iterator = iter(observed)
    return all(any(actual == wanted for actual in iterator) for wanted in expected)


def signals_match(expected: list[str], observed: list[str], mode: str = "ordered") -> bool:
    """Match ordered workflows or unordered required-source coverage.

    A multi-source answer can obtain calendar evidence before chat evidence;
    forcing an order there would turn a valid trajectory into a false miss.
    Duplicate expected names still require the same number of observations.
    """
    if mode == "ordered":
        return is_subsequence(expected, observed)
    if mode == "all":
        observed_counts = Counter(observed)
        return all(observed_counts[name] >= count for name, count in Counter(expected).items())
    raise ValueError(f"unsupported signal_match_mode: {mode}")


def load_matrix(path: Path) -> dict[str, Any]:
    matrix = json.loads(path.read_text())
    if not isinstance(matrix, dict) or not isinstance(matrix.get("scenarios"), list):
        raise ValueError("matrix must be an object containing scenarios")
    return matrix


def select_scenarios(matrix: dict[str, Any], requested_ids: set[str] | None) -> dict[str, Any]:
    if requested_ids is None:
        return matrix
    known_ids = {scenario.get("id") for scenario in matrix["scenarios"]}
    unknown = sorted(requested_ids - known_ids)
    if unknown:
        raise ValueError(f"unknown scenario IDs: {', '.join(unknown)}")
    return {**matrix, "scenarios": [scenario for scenario in matrix["scenarios"] if scenario["id"] in requested_ids]}


def trial_report(scenario: dict[str, Any], trial: int, run_root: Path) -> dict[str, Any]:
    case_id = f"{scenario['id']}-trial-{trial:02d}"
    atif_paths = sorted((run_root / case_id / "relay" / "atif").glob("*.json"))
    if not atif_paths:
        return {"case_id": case_id, "trial": trial, "status": "not_collected"}
    if len(atif_paths) != 1:
        return {
            "case_id": case_id,
            "trial": trial,
            "status": "ambiguous_atif",
            "atif_file_count": len(atif_paths),
        }
    try:
        run = extract_run(case_id, json.loads(atif_paths[0].read_text()))
    except (OSError, ValueError, json.JSONDecodeError):
        # Keep the coverage report safe to hand to a reviewer. Error strings
        # may interpolate untrusted fields from malformed input.
        return {"case_id": case_id, "trial": trial, "status": "unreadable_atif"}
    observed = [call["name"] for call in run["calls"]]
    signals = scenario.get("signals", [])
    mode = scenario.get("signal_match_mode", "ordered")
    if mode not in {"ordered", "all"}:
        raise ValueError(f"unsupported signal_match_mode: {mode}")
    return {
        "case_id": case_id,
        "trial": trial,
        "status": "signals_matched" if signals_match(signals, observed, mode) else "signals_missing",
        "expected_signals": signals,
        "signal_match_mode": mode,
        "observed_tools": observed,
    }


def report(matrix: dict[str, Any], matrix_path: Path, run_root: Path, trials: int, arm: str) -> dict[str, Any]:
    scenarios = []
    all_trials_good = True
    for scenario in matrix["scenarios"]:
        records = [trial_report(scenario, trial, run_root) for trial in range(1, trials + 1)]
        matched = sum(record["status"] == "signals_matched" for record in records)
        scenarios.append(
            {
                "scenario_id": scenario["id"],
                "expected_trials": trials,
                "signal_matched_trials": matched,
                "trials": records,
            }
        )
        all_trials_good = all_trials_good and matched == trials
    return {
        "schema_version": "fidelity-coverage-report-v1",
        "matrix_path": str(matrix_path),
        "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "arm": arm,
        "run_root": str(run_root),
        "all_expected_signals_matched": all_trials_good,
        "interpretation": "Collection completeness only; review real traces in NeMo Insights before assigning failure labels.",
        "scenarios": scenarios,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=ROOT / "experiments" / "fidelity-matrix.json")
    parser.add_argument("--arm", choices=["baseline", "candidate"], default="baseline")
    parser.add_argument("--run-root", type=Path, help="Defaults to .runs/<arm>")
    parser.add_argument("--trials", type=int, help="Defaults to matrix baseline trial count")
    parser.add_argument("--scenario", action="append", help="Scenario ID to check; may be repeated")
    parser.add_argument("--output", type=Path, help="Defaults to <run-root>/fidelity-coverage-report.json")
    args = parser.parse_args()

    matrix = select_scenarios(load_matrix(args.matrix), set(args.scenario) if args.scenario else None)
    trials = args.trials if args.trials is not None else matrix.get("go_no_go", {}).get("baseline_trials_per_scenario", 5)
    if not isinstance(trials, int) or trials < 1:
        raise SystemExit("error: trials must be a positive integer")
    run_root = args.run_root or ROOT / ".runs" / args.arm
    coverage = report(matrix, args.matrix, run_root, trials, args.arm)
    output = args.output or run_root / "fidelity-coverage-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(coverage, indent=2) + "\n")
    print(f"Wrote coverage report: {output}")
    return 0 if coverage["all_expected_signals_matched"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        raise SystemExit(f"error: {error}")
