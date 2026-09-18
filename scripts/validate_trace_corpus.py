#!/usr/bin/env python3
"""Validate the checked-in ATIF corpus and its index."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_CASES = {
    "source-coverage",
    "read-after-search",
    "bounded-retry",
    "auth-awareness",
    "approval-boundary",
    "bounded-structured-inspection",
}


def validate(index_path: Path, *, per_case: int = 6) -> list[str]:
    errors: list[str] = []
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("schema") != "enterprise-trace-corpus-v1":
        errors.append("unsupported corpus schema")
    records = index.get("traces")
    if not isinstance(records, list):
        return errors + ["traces must be a list"]

    counts: Counter[str] = Counter()
    seen_paths: set[str] = set()
    seen_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            errors.append("every index record must be an object")
            continue
        raw_path = record.get("path")
        if not isinstance(raw_path, str) or Path(raw_path).is_absolute() or ".." in Path(raw_path).parts:
            errors.append(f"invalid relative trace path: {raw_path!r}")
            continue
        if raw_path in seen_paths:
            errors.append(f"duplicate trace path: {raw_path}")
        seen_paths.add(raw_path)
        trace_path = index_path.parent / raw_path
        if not trace_path.is_file():
            errors.append(f"missing trace: {raw_path}")
            continue
        trace: dict[str, Any] = json.loads(trace_path.read_text(encoding="utf-8"))
        if trace.get("schema_version") != "ATIF-v1.7":
            errors.append(f"{raw_path}: expected ATIF-v1.7")
        trace_id = trace.get("trajectory_id")
        if trace_id != record.get("trace_id"):
            errors.append(f"{raw_path}: trace_id does not match trajectory_id")
        if trace_id in seen_ids:
            errors.append(f"duplicate trajectory_id: {trace_id}")
        seen_ids.add(trace_id)
        case_id = record.get("logical_case_id")
        if case_id != trace.get("extra", {}).get("logical_case_id"):
            errors.append(f"{raw_path}: logical_case_id mismatch")
        counts[str(case_id)] += 1

    if set(counts) != EXPECTED_CASES:
        errors.append(f"case IDs differ: found {sorted(counts)}")
    for case_id in sorted(EXPECTED_CASES):
        if counts[case_id] != per_case:
            errors.append(f"{case_id}: expected {per_case} traces, found {counts[case_id]}")
    if len(records) != len(EXPECTED_CASES) * per_case:
        errors.append(f"expected {len(EXPECTED_CASES) * per_case} traces, found {len(records)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--per-case", type=int, default=6)
    args = parser.parse_args()
    errors = validate(args.index, per_case=args.per_case)
    if errors:
        print("Trace corpus validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Trace corpus validation passed: {args.per_case * len(EXPECTED_CASES)} traces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
