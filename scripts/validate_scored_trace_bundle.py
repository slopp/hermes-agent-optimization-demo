#!/usr/bin/env python3
"""Validate the checked-in canonical Trace Analyst development bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    traces = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    ids = [trace.get("id") for trace in traces]
    cases = [trace.get("attributes", {}).get("logical_case_id") for trace in traces]
    rewards = [trace.get("evaluator_results", {}).get("harbor.reward") for trace in traces]
    if len(traces) != 6:
        errors.append(f"expected 6 traces, found {len(traces)}")
    if len(set(ids)) != len(ids) or any(not value for value in ids):
        errors.append("trace IDs must be present and unique")
    if len(set(cases)) != 6 or any(not value for value in cases):
        errors.append("expected six distinct logical case IDs")
    if any(value not in {0, 1} for value in rewards):
        errors.append("every trace needs a binary harbor.reward")
    if rewards.count(1.0) != 1:
        errors.append(f"expected one passing baseline trace, found {rewards.count(1.0)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors = validate(args.path)
    if errors:
        print("Scored trace bundle validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Scored trace bundle validation passed: 6 traces, 1 pass, 5 failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
